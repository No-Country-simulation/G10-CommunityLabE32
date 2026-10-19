"""Contrato de fechas: ISO 8601 + zona IANA → intervalo UTC [inicio, fin).

- Solo fecha (AAAA-MM-DD): «desde» = primer instante de ese día en la zona; «hasta» = primer
  instante del día SIGUIENTE (incluye el día completo). Se calcula con el calendario local, no
  sumando 24 h: respeta días de 23 o 25 h y medianoches inexistentes (el día empieza en el primer
  instante cuya fecha local es la pedida, p. ej. 01:00 en America/Sao_Paulo el 2018-11-04).
  Si la fecha local pedida no existe en la zona (p. ej. 2011-12-30 en Pacific/Apia), se rechaza.
- Fecha y hora sin desplazamiento: hora local de la zona. Una hora inexistente por cambio de
  horario se rechaza; una ambigua usa la primera ocurrencia y lo advierte.
- Fecha y hora con desplazamiento (Z o ±HH:MM): instante exacto; la zona solo sirve para mostrar.
- Se persiste y compara en UTC.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

EPOCH_DISCORD_MS = 1420070400000  # 2015-01-01T00:00:00Z (documentación oficial de snowflakes)
INICIO_DISCORD = datetime.fromtimestamp(EPOCH_DISCORD_MS / 1000, timezone.utc)
_SOLO_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SNOWFLAKE = re.compile(r"^\d{17,20}$")


class RangoInvalido(ValueError):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo, self.mensaje = codigo, mensaje


@dataclass(frozen=True)
class Rango:
    inicio_utc: datetime
    fin_utc: datetime            # exclusivo
    zona: str
    inicio_local: str
    fin_local: str
    advertencias: tuple = field(default_factory=tuple)

    @property
    def dias(self):
        return (self.fin_utc - self.inicio_utc).total_seconds() / 86400

    def como_dict(self):
        return {"inicio_utc": iso(self.inicio_utc), "fin_utc_exclusivo": iso(self.fin_utc),
                "zona": self.zona, "inicio_local": self.inicio_local, "fin_local_exclusivo": self.fin_local,
                "dias": round(self.dias, 3)}


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def es_snowflake(valor):
    return isinstance(valor, str) and bool(_SNOWFLAKE.match(valor))


def snowflake_de(dt):
    """Snowflake límite para un instante: (ms − epoch) << 22 (documentación oficial)."""
    ms = int(dt.astimezone(timezone.utc).timestamp() * 1000)
    return str(max(0, ms - EPOCH_DISCORD_MS) << 22)


def fecha_de_snowflake(snowflake):
    return datetime.fromtimestamp(((int(snowflake) >> 22) + EPOCH_DISCORD_MS) / 1000, timezone.utc)


def zona_iana(nombre):
    if not isinstance(nombre, str) or not nombre.strip() or len(nombre) > 64 or ".." in nombre:
        raise RangoInvalido("zona_invalida", "La zona horaria debe ser un nombre IANA, por ejemplo America/Guatemala.")
    try:
        return ZoneInfo(nombre.strip())
    except (ZoneInfoNotFoundError, ValueError):
        raise RangoInvalido("zona_invalida", f"Zona horaria desconocida: use un nombre IANA (p. ej. America/Guatemala).") from None


def _local_a_utc(local, zona, campo, advertencias):
    """Fecha-hora local con hora explícita → UTC. Inexistente: error; ambigua: primera ocurrencia."""
    a = local.replace(tzinfo=zona, fold=0)
    b = local.replace(tzinfo=zona, fold=1)
    ua, ub = a.astimezone(timezone.utc), b.astimezone(timezone.utc)
    if not any(u.astimezone(zona).replace(tzinfo=None) == local for u in (ua, ub)):
        raise RangoInvalido("hora_inexistente",
                            f"{campo}: esa hora no existe en {zona.key} por un cambio de horario.")
    if ua != ub:
        advertencias.append(f"{campo}_ambigua_se_uso_la_primera_ocurrencia")
    return ua  # fold=0 = primera ocurrencia (PEP 495)


def primer_instante_del_dia(dia, zona):
    """Primer instante UTC cuya fecha local en `zona` es `dia` o posterior.

    Búsqueda binaria por segundos entre dos días antes y dos después: no depende de cómo resuelva
    `fold` una hora inexistente, sirve tanto si el salto empieza a medianoche como antes de ella,
    y en una medianoche repetida devuelve la primera. Supone que la fecha local no retrocede
    (cierto en tzdata salvo transiciones históricas que cruzan la medianoche hacia atrás).
    """
    base = datetime.combine(dia, time(), tzinfo=timezone.utc)
    lo = int((base - timedelta(days=2)).timestamp())   # fecha local < dia
    hi = int((base + timedelta(days=2)).timestamp())   # fecha local >= dia
    while hi - lo > 1:
        medio = (lo + hi) // 2
        if datetime.fromtimestamp(medio, zona).date() >= dia:
            hi = medio
        else:
            lo = medio
    return datetime.fromtimestamp(hi, timezone.utc)


def _inicio_de_fecha(dia, zona, campo, advertencias, es_fin):
    u = primer_instante_del_dia(dia, zona)
    local = u.astimezone(zona)
    pedido = dia - timedelta(days=1) if es_fin else dia   # «hasta» pide el día anterior completo
    if primer_instante_del_dia(pedido, zona).astimezone(zona).date() != pedido:
        raise RangoInvalido("fecha_local_inexistente",
                            f"{campo}: el día {pedido.isoformat()} no existe en {zona.key} (cambio de zona horaria).")
    if local.date() == dia and local.time() != time():
        advertencias.append(f"{campo}_inicio_del_dia_ajustado_por_cambio_de_horario")
    else:
        pared = local.replace(tzinfo=None)
        otra = pared.replace(tzinfo=zona, fold=1).astimezone(timezone.utc)
        if otra != u and otra.astimezone(zona).replace(tzinfo=None) == pared:   # medianoche repetida
            advertencias.append(f"{campo}_ambigua_se_uso_la_primera_ocurrencia")
    return u


def _interpretar(valor, zona, campo, es_fin, advertencias):
    if not isinstance(valor, str) or not valor.strip() or len(valor) > 40:
        raise RangoInvalido("fecha_invalida", f"{campo}: obligatorio, en ISO 8601.")
    v = valor.strip()
    if _SOLO_FECHA.match(v):
        try:
            d = date.fromisoformat(v)
        except ValueError:
            raise RangoInvalido("fecha_invalida", f"{campo}: fecha inexistente.") from None
        if es_fin:
            d += timedelta(days=1)  # día completo: el límite exclusivo es el inicio del día siguiente local
        return _inicio_de_fecha(d, zona, campo, advertencias, es_fin)
    try:
        dt = datetime.fromisoformat(v[:-1] + "+00:00" if v.endswith(("Z", "z")) else v)
    except ValueError:
        raise RangoInvalido("fecha_invalida",
                            f"{campo}: use AAAA-MM-DD o AAAA-MM-DDTHH:MM[:SS][Z|±HH:MM].") from None
    if dt.tzinfo is None:
        return _local_a_utc(dt, zona, campo, advertencias)
    return dt.astimezone(timezone.utc)


def normalizar_rango(desde, hasta, zona, ahora, max_dias):
    """Valida y normaliza. `ahora` (UTC) congela el final: no entra nada posterior."""
    tz = zona_iana(zona)
    advertencias = []
    inicio = _interpretar(desde, tz, "desde", False, advertencias)
    fin = _interpretar(hasta, tz, "hasta", True, advertencias)
    if inicio >= fin:
        raise RangoInvalido("rango_invertido", "«desde» debe ser anterior a «hasta».")
    if inicio >= ahora:
        raise RangoInvalido("fecha_futura", "«desde» no puede estar en el futuro.")
    if fin > ahora:
        fin = ahora.replace(microsecond=0)
        advertencias.append("hasta_recortado_al_momento_de_la_solicitud")
    if fin <= INICIO_DISCORD:
        raise RangoInvalido("rango_anterior_a_discord", "El rango termina antes de 2015-01-01, cuando no existían mensajes de Discord.")
    if inicio < INICIO_DISCORD:
        inicio = INICIO_DISCORD
        advertencias.append("desde_ajustado_al_inicio_de_discord_2015")
    dias = (fin - inicio).total_seconds() / 86400
    if dias > max_dias:
        raise RangoInvalido("rango_excesivo", f"El rango supera el máximo de {max_dias} días.")
    return Rango(inicio, fin, tz.key, inicio.astimezone(tz).isoformat(), fin.astimezone(tz).isoformat(),
                 tuple(advertencias))
