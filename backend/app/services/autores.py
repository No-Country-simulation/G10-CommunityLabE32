"""Nombre para mostrar de un autor: el visible si existe; nunca un ID numérico como si fuera una persona."""
from pipelines.communitylab.autores import nombre_visible


def visible(autor, autor_nombre=None):
    return nombre_visible({"autor": autor, "autor_nombre": autor_nombre})
