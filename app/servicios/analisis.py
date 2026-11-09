"""Series para gráficas, cambios de agua y predicción (CLAUDE.md, 7.5 y 8.1)."""

from datetime import datetime, timedelta
from decimal import Decimal
from itertools import pairwise

from fastapi import status
from sqlalchemy.orm import Session

from app.dominio import prediccion as modelo
from app.dominio.series import (
    INTERVALOS,
    MAX_PUNTOS,
    cantidad_de_intervalos,
    intervalo_automatico,
    promediar,
)
from app.esquemas.analisis import (
    CambioAguaCrear,
    CambioAguaSalida,
    EvaluacionSalida,
    PrediccionSalida,
    PuntoSerie,
    Serie,
)
from app.esquemas.control import Pagina
from app.modelos import CambioAgua, Prediccion, Tanque, Usuario
from app.repositorios import analisis as repo
from app.repositorios.control import variables_por_codigo
from app.servicios.errores import ErrorDeNegocio

RANGO_MAXIMO = timedelta(days=31)
RANGO_PREDETERMINADO = timedelta(hours=24)
TOLERANCIA_FUTURO = timedelta(seconds=60)
VIGENCIA_PREDICCION_GUARDADA = timedelta(hours=1)
_SEGUNDOS_POR_DIA = 86400

# La evaluación recorre un ciclo completo; su resultado no cambia mientras no cambien los ciclos.
_cache_evaluaciones: dict[tuple, modelo.Evaluacion | None] = {}


def _obtener_tanque(sesion: Session, tanque_id: int) -> Tanque:
    tanque = sesion.get(Tanque, tanque_id)
    if tanque is None:
        raise ErrorDeNegocio(
            status.HTTP_404_NOT_FOUND, "TANQUE_NO_ENCONTRADO", "No existe ese tanque."
        )
    return tanque


def _invalido(code: str, message: str) -> ErrorDeNegocio:
    return ErrorDeNegocio(status.HTTP_422_UNPROCESSABLE_CONTENT, code, message)


def serie(
    sesion: Session,
    tanque_id: int,
    codigo_variable: str,
    desde: datetime | None,
    hasta: datetime | None,
    intervalo: str | None,
    incluir_desconocidas: bool,
    ahora: datetime,
) -> Serie:
    """Promedio por intervalo de una variable del tanque, calculado en el servidor."""
    _obtener_tanque(sesion, tanque_id)
    variable = variables_por_codigo(sesion, [codigo_variable]).get(codigo_variable)
    if variable is None:
        raise ErrorDeNegocio(
            status.HTTP_404_NOT_FOUND, "VARIABLE_NO_ENCONTRADA", "No existe esa variable."
        )
    hasta = hasta or ahora
    desde = desde or hasta - RANGO_PREDETERMINADO
    if desde >= hasta:
        raise _invalido("RANGO_INVALIDO", "La fecha inicial debe ser anterior a la final.")
    if hasta - desde > RANGO_MAXIMO:
        raise _invalido("RANGO_DEMASIADO_GRANDE", "El rango máximo es de 31 días.")
    intervalo = intervalo or intervalo_automatico(desde, hasta)
    if cantidad_de_intervalos(desde, hasta, INTERVALOS[intervalo]) > MAX_PUNTOS:
        raise _invalido(
            "DEMASIADOS_PUNTOS",
            f"Con ese intervalo saldrían más de {MAX_PUNTOS} puntos; usa uno mayor.",
        )

    sensor_id = repo.sensor_de_tanque(sesion, tanque_id, codigo_variable)
    lecturas = (
        repo.lecturas_de_sensor(sesion, sensor_id, desde, hasta, incluir_desconocidas)
        if sensor_id is not None
        else []
    )
    puntos = [
        PuntoSerie(t=inicio, valor=round(promedio, 3), muestras=muestras)
        for inicio, promedio, muestras in promediar(lecturas, desde, INTERVALOS[intervalo])
    ]
    return Serie(
        variable=variable.codigo,
        nombre=variable.nombre,
        unidad=variable.unidad,
        tipo=variable.tipo.value,
        intervalo=intervalo,
        desde=desde,
        hasta=hasta,
        puntos=puntos,
    )


def _cambio_a_salida(cambio: CambioAgua) -> CambioAguaSalida:
    return CambioAguaSalida(
        id=cambio.id,
        tanque_id=cambio.tanque_id,
        realizado_en=cambio.realizado_en,
        porcentaje=float(cambio.porcentaje),
        registrado_por=cambio.registrado_por,
    )


def registrar_cambio(
    sesion: Session, tanque_id: int, datos: CambioAguaCrear, usuario: Usuario, ahora: datetime
) -> CambioAguaSalida:
    """Un cambio de agua, parcial o total, cierra el ciclo actual y abre uno nuevo."""
    _obtener_tanque(sesion, tanque_id)
    realizado_en = datos.realizado_en or ahora
    if realizado_en > ahora + TOLERANCIA_FUTURO:
        raise _invalido("FECHA_FUTURA", "El cambio de agua no puede estar en el futuro.")
    anteriores = repo.cambios_de_tanque(sesion, tanque_id)
    if anteriores and realizado_en <= anteriores[-1].realizado_en:
        raise _invalido(
            "FECHA_ANTERIOR_AL_ULTIMO_CAMBIO",
            "Debe ser posterior al último cambio de agua registrado.",
        )
    cambio = CambioAgua(
        tanque_id=tanque_id,
        realizado_en=realizado_en,
        porcentaje=datos.porcentaje,
        registrado_por=usuario.id,
    )
    sesion.add(cambio)
    sesion.commit()
    return _cambio_a_salida(cambio)


def listar_cambios(
    sesion: Session, tanque_id: int, pagina: int, tamano: int
) -> Pagina[CambioAguaSalida]:
    _obtener_tanque(sesion, tanque_id)
    filas, total = repo.listar_cambios(sesion, tanque_id, (pagina - 1) * tamano, tamano)
    return Pagina(
        elementos=[_cambio_a_salida(c) for c in filas], total=total, pagina=pagina, tamano=tamano
    )


def _evaluacion(
    sesion: Session, sensor_id: int, cambios: list[CambioAgua], limite: float
) -> modelo.Evaluacion | None:
    if len(cambios) < 2:
        return None
    fechas = [c.realizado_en for c in cambios]
    llave = (sensor_id, tuple(fechas), limite)
    if llave not in _cache_evaluaciones:
        # Solo el último ciclo completo necesita lecturas; los anteriores aportan su duración.
        ciclos = [modelo.Ciclo(inicio, fin, []) for inicio, fin in pairwise(fechas[:-1])]
        inicio, fin = fechas[-2], fechas[-1]
        ciclos.append(
            modelo.Ciclo(inicio, fin, repo.lecturas_de_sensor(sesion, sensor_id, inicio, fin))
        )
        _cache_evaluaciones[llave] = modelo.evaluar(ciclos, limite)
    return _cache_evaluaciones[llave]


def _guardar_si_corresponde(
    sesion: Session,
    cambio: CambioAgua,
    ajuste: modelo.Ajuste,
    limite: float,
    baseline: float | None,
    ahora: datetime,
) -> datetime:
    """Guarda como máximo una predicción por hora y por ciclo; devuelve cuándo se generó."""
    ultima = repo.ultima_prediccion(sesion, cambio.id)
    if ultima is not None and ahora - ultima.generada_en < VIGENCIA_PREDICCION_GUARDADA:
        return ultima.generada_en
    sesion.add(
        Prediccion(
            cambio_agua_id=cambio.id,
            generada_en=ahora,
            modelo_version=modelo.MODELO_VERSION,
            pendiente=Decimal(str(round(ajuste.pendiente_ppm_h, 6))),
            intercepto=Decimal(str(round(ajuste.intercepto_ppm, 6))),
            limite_tds=Decimal(str(limite)),
            r2=Decimal(str(round(ajuste.r2, 6))) if ajuste.r2 is not None else None,
            n_muestras=ajuste.n_muestras,
            baseline_dias=Decimal(str(round(baseline, 3))) if baseline is not None else None,
        )
    )
    sesion.commit()
    return ahora


def predecir(sesion: Session, tanque_id: int, ahora: datetime) -> PrediccionSalida:
    """Días estimados hasta el próximo cambio de agua. Nunca inventa un número."""
    _obtener_tanque(sesion, tanque_id)
    cambios = list(repo.cambios_de_tanque(sesion, tanque_id))
    if not cambios:
        raise ErrorDeNegocio(
            status.HTTP_409_CONFLICT,
            "SIN_CAMBIOS_DE_AGUA",
            "El tanque no tiene cambios de agua registrados.",
        )
    actual = cambios[-1]
    inicio = actual.realizado_en
    transcurridos = max(0.0, (ahora - inicio).total_seconds() / _SEGUNDOS_POR_DIA)
    baseline = modelo.duracion_promedio_dias([c.realizado_en for c in cambios])
    limite = repo.limite_tds(sesion, tanque_id)
    sensor_id = repo.sensor_de_tanque(sesion, tanque_id, "tds_ppm")

    ajuste = None
    if sensor_id is not None:
        ajuste = modelo.ajustar(inicio, repo.lecturas_de_sensor(sesion, sensor_id, inicio, ahora))
    cruce = modelo.momento_de_cruce(inicio, ajuste, limite) if ajuste and limite else None

    if sensor_id is None:
        motivo = "SIN_SENSOR_TDS"
    elif limite is None:
        motivo = "SIN_UMBRAL_TDS"
    elif ajuste is None:
        motivo = modelo.MOTIVO_POCOS_DATOS
    elif cruce is None:
        motivo = modelo.MOTIVO_PENDIENTE_NO_POSITIVA
    else:
        motivo = None

    generada_en = None
    if cruce is not None and ajuste is not None and limite is not None:
        generada_en = _guardar_si_corresponde(sesion, actual, ajuste, limite, baseline, ahora)
    evaluacion = (
        _evaluacion(sesion, sensor_id, cambios, limite)
        if sensor_id is not None and limite is not None
        else None
    )

    return PrediccionSalida(
        estado="confiable" if motivo is None else "no_confiable",
        motivo=motivo,
        ciclo_iniciado_en=inicio,
        dias_transcurridos=round(transcurridos, 2),
        dias_restantes=round(modelo.dias_restantes(cruce, ahora), 2) if cruce else None,
        fecha_estimada=cruce,
        baseline_dias=round(baseline, 2) if baseline is not None else None,
        baseline_dias_restantes=(
            round(max(0.0, baseline - transcurridos), 2) if baseline is not None else None
        ),
        limite_tds=limite,
        pendiente_ppm_por_dia=round(ajuste.pendiente_ppm_h * 24, 2) if ajuste else None,
        r2=round(ajuste.r2, 3) if ajuste and ajuste.r2 is not None else None,
        n_muestras=ajuste.n_muestras if ajuste else 0,
        horas_de_datos=round(ajuste.horas_de_datos, 1) if ajuste else 0.0,
        modelo_version=modelo.MODELO_VERSION,
        generada_en=generada_en,
        evaluacion=EvaluacionSalida(
            mae_modelo_dias=round(evaluacion.mae_modelo_dias, 2)
            if evaluacion.mae_modelo_dias is not None
            else None,
            mae_baseline_dias=round(evaluacion.mae_baseline_dias, 2)
            if evaluacion.mae_baseline_dias is not None
            else None,
            predicciones_evaluadas=evaluacion.predicciones_evaluadas,
        )
        if evaluacion
        else None,
    )
