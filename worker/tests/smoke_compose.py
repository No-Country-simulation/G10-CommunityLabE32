"""Prueba local real por HTTP. Ejecutar con dos workers; solo usa datos sintéticos."""
import json
import time
from pathlib import Path
import requests
from worker.tests.test_worker import lote

BASE = 'http://127.0.0.1:18092'


def comprobar():
    resultados = []
    for ruta in ['/', '/ingesta', '/interacciones', '/curaduria', '/api/dashboard/kpis']:
        r = requests.get(BASE + ruta, timeout=15)
        assert r.status_code == 200, (ruta, r.status_code, r.text[:300])
    for numero in range(4):
        entrada = lote()
        if numero == 0:
            r = requests.post(BASE + '/api/mensajes/procesamientos',
                files={'file': ('prueba.json', json.dumps(entrada['interacciones']).encode())},
                data={'origen_comunidad': entrada['origen_comunidad'],
                      'periodo_referencia': entrada['periodo_referencia'], 'cierre_periodo': 'true'}, timeout=15)
        else:
            r = requests.post(BASE + '/api/v1/trabajos', json=entrada, timeout=15)
        assert r.status_code == 202, r.text
        resultados.append((r.json()['consulta'], entrada))
    for consulta, entrada in resultados:
        limite = time.monotonic() + 40
        while True:
            r = requests.get(BASE + consulta, timeout=10)
            r.raise_for_status()
            estado = r.json()
            if estado['estado'] in {'terminado', 'error'}:
                break
            assert time.monotonic() < limite, estado
            time.sleep(0.3)
        assert estado['estado'] == 'terminado', estado
        assert estado['historial'] == ['recibido', 'procesando', 'terminado']
        assert estado['intentos'] == 1
        salida = estado['resultado']
        assert salida['simulado'] is True and not salida['errores']
        assert len(salida['activos_distribucion_generados']) == 3
        bloqueo = entrada['interacciones'][-1]['id']
        assert all(bloqueo not in a['fuentes'] for a in salida['activos_distribucion_generados'])
    activos = requests.get(BASE + '/api/curaduria/activos?limit=100', timeout=10).json()['items']
    fuentes = {m['id'] for _, e in resultados for m in e['interacciones']}
    nuevos = [a for a in activos if fuentes.intersection(a['fuentes'])]
    assert len(nuevos) == 12
    for a in nuevos:
        detalle = requests.get(BASE + '/api/curaduria/activos/' + a['id_activo'], timeout=10).json()
        assert {f['id_mensaje'] for f in detalle['fuentes_detalle']} == set(a['fuentes'])
    evidencia = {'resultado': 'APROBADO', 'lotes': 4, 'activos': 12,
        'simulado': True, 'consultas': [c for c, _ in resultados],
        'comprobaciones': ['cinco rutas HTTP', 'carga JSON y tres lotes por API',
            'historial y un intento por lote', 'fuentes reales en curaduria', 'bloqueos excluidos']}
    destino = Path('../evidencias/smoke-compose.json')
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(evidencia, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(evidencia, ensure_ascii=False))


if __name__ == '__main__':
    comprobar()
