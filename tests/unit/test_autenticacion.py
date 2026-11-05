import pytest

from app.servicios.autenticacion import validar_contrasena_nueva


def test_rechaza_contrasena_de_menos_de_12_caracteres():
    with pytest.raises(ValueError, match="12"):
        validar_contrasena_nueva("x" * 11)


def test_acepta_contrasena_de_12_caracteres():
    validar_contrasena_nueva("x" * 12)


def test_rechaza_contrasena_de_mas_de_72_bytes_aunque_tenga_menos_caracteres():
    with pytest.raises(ValueError, match="72"):
        validar_contrasena_nueva("ñ" * 40)
