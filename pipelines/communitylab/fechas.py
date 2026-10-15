"""Contrato de fechas compartido por Discord y la cola HTTP."""
from datetime import datetime, timezone
import re


def fecha_utc(valor):
    """Exige fecha/hora ISO 8601 con zona explícita y devuelve UTC."""
    if not isinstance(valor, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", valor
    ):
        raise ValueError("fecha: se requiere ISO 8601 con hora y zona horaria")
    # datetime admite offsets fuera del rango de minutos en algunas versiones.
    if not valor.endswith('Z') and (int(valor[-5:-3]) > 23 or int(valor[-2:]) > 59):
        raise ValueError("fecha: zona horaria inválida")
    try:
        return datetime.fromisoformat(valor.replace('Z', '+00:00')).astimezone(timezone.utc).isoformat()
    except (ValueError, OverflowError):
        raise ValueError("fecha: fecha u hora inválida") from None
