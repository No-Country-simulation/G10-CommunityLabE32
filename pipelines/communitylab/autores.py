"""Nombre visible de un autor. Sin dependencias: lo usan el grafo, la API y los scripts."""
import re

# IDs de Discord (u otros numéricos largos) no son nombres: nunca se muestran ni se redacta con ellos.
ID_NUMERICO = re.compile(r"^\d{15,21}$")
SIN_NOMBRE = "Miembro de la comunidad"


def nombre_visible(mensaje):
    """autor_nombre si existe; si no, el autor, salvo que sea un ID numérico."""
    nombre = " ".join(str(mensaje.get("autor_nombre") or "").split())
    if nombre:
        return nombre
    autor = str(mensaje.get("autor") or "").strip()
    return SIN_NOMBRE if not autor or ID_NUMERICO.match(autor) else autor
