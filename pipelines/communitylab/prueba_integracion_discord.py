"""
Envía mensajes de Discord normalizados a POST /api/v1/trabajos y espera su estado final.

Uso:
    python prueba_integracion_discord.py --simulado              # datos ficticios en un archivo temporal
    python prueba_integracion_discord.py --archivo export.jsonl  # exportación real del lector (solo lectura)

Códigos de salida: 0 todo terminado, 1 error del backend o trabajo fallido,
2 sin conexión o tiempo agotado, 3 entrada inválida.
La salida no usa emojis para funcionar en terminales CP1252 y UTF-8.
"""
import argparse
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
import sqlite3
from pathlib import Path

try:
    from .normalizador_discord import construir_lotes, normalizar_discord_jsonl
    from .entregas_discord import Entregas
except ImportError:  # ejecutado como script desde esta carpeta
    from normalizador_discord import construir_lotes, normalizar_discord_jsonl
    from entregas_discord import Entregas

URL_BACKEND = os.environ.get("URL_BACKEND", "http://localhost:8000/api/v1/trabajos")
ESTADOS_FINALES = {"terminado", "error"}

SALIDA_OK, SALIDA_ERROR_BACKEND, SALIDA_SIN_CONEXION, SALIDA_ENTRADA_INVALIDA = 0, 1, 2, 3


class ErrorBackend(Exception):
    pass


class SinConexion(Exception):
    pass


def mensajes_simulados():
    """Simula la salida exportada del lector de Paulo (export_jsonl), con un duplicado intencional."""
    base = {"schema_version": "discord-source-v1", "guild_id": "111111111111111111",
            "channel_id": "222222222222222222"}
    mensajes = [
        {**base, "message_id": "999999999999999991", "author_id": "user_4444",
         "created_at": "2026-10-12T10:00:00+00:00",
         "content": "¡Hola equipo! Logré configurar la máquina en Oracle Cloud, ¡estoy feliz!"},
        {**base, "message_id": "999999999999999992", "author_id": "user_5555",
         "created_at": "2026-10-12T10:05:00+00:00",
         "content": "Tengo un problema con Docker, me tira error 500 al levantar la API."},
    ]
    return mensajes + [mensajes[0]]


def escribir_simulados_temporal():
    """Crea un archivo temporal propio; nunca toca un discord_export.jsonl existente."""
    descriptor, ruta = tempfile.mkstemp(prefix="discord_simulado_", suffix=".jsonl")
    with os.fdopen(descriptor, "w", encoding="utf-8") as f:
        for msg in mensajes_simulados():
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")
    return ruta


def _pedir(url, datos=None, timeout=10, clave=None):
    cuerpo = None if datos is None else json.dumps(datos, ensure_ascii=False).encode("utf-8")
    peticion = urllib.request.Request(url, data=cuerpo, method="POST" if cuerpo else "GET",
                                      headers={"Content-Type": "application/json; charset=utf-8"})
    if clave:
        peticion.add_header('Idempotency-Key', clave)
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            resultado = json.loads(respuesta.read().decode("utf-8"))
            if not isinstance(resultado, dict):
                raise ErrorBackend('Respuesta JSON no es un objeto')
            return resultado
    except (ValueError, UnicodeError):
        raise ErrorBackend('Respuesta JSON inválida') from None
    except urllib.error.HTTPError as error:
        detalle = error.read().decode("utf-8", "replace")[:300]
        raise ErrorBackend(f"HTTP {error.code}: {detalle}") from None
    except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
        raise SinConexion(str(getattr(error, "reason", error))) from None


def enviar_lote(url, lote, clave=None):
    """Envía un lote y devuelve el id del procesamiento."""
    respuesta = _pedir(url, lote, clave=clave)
    identificador = respuesta.get("procesamiento_id")
    if not isinstance(identificador, str) or not identificador:
        raise ErrorBackend(f"respuesta sin procesamiento_id: {respuesta}")
    return identificador


def esperar_estado_final(url, identificador, espera_maxima=180, intervalo=2):
    """Consulta el trabajo hasta que termine; devuelve su estado final."""
    limite = time.monotonic() + espera_maxima
    while True:
        restante = limite - time.monotonic()
        estado = _pedir(f"{url.rstrip('/')}/{identificador}", timeout=max(.1, min(10, restante))).get("estado")
        if estado in ESTADOS_FINALES:
            return estado
        if time.monotonic() >= limite:
            raise SinConexion(f"tiempo agotado esperando el trabajo {identificador} (estado={estado})")
        time.sleep(min(intervalo, max(0, limite - time.monotonic())))


def ejecutar(argv=None, salida=print):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    fuente = parser.add_mutually_exclusive_group(required=True)
    fuente.add_argument("--archivo", help="ruta de una exportación real del lector (no se modifica)")
    fuente.add_argument("--simulado", action="store_true", help="usar mensajes ficticios en un archivo temporal")
    parser.add_argument("--url", default=URL_BACKEND)
    parser.add_argument("--origen", default="discord")
    parser.add_argument("--periodo", default=os.environ.get("PERIODO_REFERENCIA", "S3"))
    parser.add_argument("--cierre", action="store_true", help="marcar el último lote como cierre de período")
    parser.add_argument("--espera", type=float, default=180, help="segundos máximos por trabajo")
    parser.add_argument("--sin-esperar", action="store_true", help="no consultar el estado final")
    parser.add_argument("--estado", help="SQLite de entregas; por defecto ARCHIVO.entregas.sqlite3")
    args = parser.parse_args(argv)

    ruta_temporal = None
    estado_temporal = None
    try:
        if args.simulado:
            ruta = ruta_temporal = escribir_simulados_temporal()
            salida("[1/3] Datos SIMULADOS en archivo temporal")
        else:
            ruta = args.archivo
            if not os.path.isfile(ruta):
                salida(f"[ERROR] No existe el archivo: {ruta}")
                return SALIDA_ENTRADA_INVALIDA
            salida(f"[1/3] Exportación REAL: {ruta}")

        resultado = normalizar_discord_jsonl(ruta)
        e = resultado["estadisticas"]
        salida(f"[2/3] Normalización: aceptados={e['aceptados']} duplicados={e['duplicados']} rechazados={e['rechazados']}")
        if e['rechazados']:
            salida('[ERROR] La exportación contiene registros inválidos; no se envió ningún lote.')
            return SALIDA_ENTRADA_INVALIDA
        if not resultado["interacciones"]:
            salida("[ERROR] No hay mensajes válidos para enviar.")
            return SALIDA_ENTRADA_INVALIDA

        if args.estado:
            ruta_estado = args.estado
        elif args.simulado:
            descriptor, estado_temporal = tempfile.mkstemp(prefix='discord_entregas_', suffix='.sqlite3')
            os.close(descriptor)
            ruta_estado = estado_temporal
        else:
            ruta_estado = str(Path(ruta).resolve()) + '.entregas.sqlite3'
        if Path(ruta_estado).resolve() == Path(ruta).resolve():
            raise ValueError('--estado no puede ser el archivo de entrada')
        entregas = Entregas(ruta_estado)
        lotes = entregas.preparar(args.url, resultado['interacciones'], args.origen,
                                  args.periodo, args.cierre, construir_lotes)
        salida(f"[3/3] Verificando {len(lotes)} entrega(s) a {args.url}")
        codigo = SALIDA_OK
        for numero, entrega in enumerate(lotes, 1):
            if entrega['estado'] == 'error':
                salida(f"[ERROR] lote {numero}: trabajo previo fallido id={entrega['trabajo']}; requiere revisión")
                return SALIDA_ERROR_BACKEND
            if entrega['estado'] == 'terminado':
                salida(f"  lote {numero}: ya terminado id={entrega['trabajo']}")
                continue
            identificador = entrega['trabajo']
            if not identificador:
                identificador = enviar_lote(args.url, json.loads(entrega['payload']), entrega['clave'])
                entregas.confirmar(entrega['clave'], identificador, 'aceptado')
            if args.sin_esperar:
                salida(f"  lote {numero}: aceptado id={identificador} (sin esperar estado final)")
                continue
            estado = esperar_estado_final(args.url, identificador, args.espera)
            entregas.confirmar(entrega['clave'], identificador, estado)
            salida(f"  lote {numero}: id={identificador} estado={estado}")
            if estado != "terminado":
                codigo = SALIDA_ERROR_BACKEND
        if args.sin_esperar:
            salida('[OK] Lotes aceptados; estado final no verificado en esta ejecución.')
        else:
            salida("[OK] Todos los lotes terminaron." if codigo == SALIDA_OK else "[ERROR] Algún lote no terminó bien.")
        return codigo
    except ErrorBackend as error:
        salida(f"[ERROR] El backend rechazó la solicitud: {error}")
        return SALIDA_ERROR_BACKEND
    except SinConexion as error:
        salida(f"[ERROR] Sin conexión con el backend: {error}")
        return SALIDA_SIN_CONEXION
    except (ValueError, OSError, sqlite3.Error) as error:
        salida(f'[ERROR] Entrada o almacenamiento local inválido: {error}')
        return SALIDA_ENTRADA_INVALIDA
    finally:
        if ruta_temporal and os.path.exists(ruta_temporal):
            os.remove(ruta_temporal)
        if estado_temporal and os.path.exists(estado_temporal):
            os.remove(estado_temporal)


if __name__ == "__main__":
    sys.exit(ejecutar())
