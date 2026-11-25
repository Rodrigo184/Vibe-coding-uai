from __future__ import annotations

from pydantic import BaseModel


class Turno(BaseModel):
    rol: str
    texto: str
    ts: float


class Episodio(BaseModel):
    fecha: str
    resumen: str


class HechoNuevo(BaseModel):
    clave: str
    valor: str
    reemplaza: bool = False
    fuente: str = ""


class Perfil(BaseModel):
    hechos: dict[str, str] = {}
    fuentes: dict[str, str] = {}
    fechas: dict[str, str] = {}
