"""Sin llamadas externas: verifica los fallos del adaptador de IA del PR16."""
import pytest
import requests
from backend.app.pipelines import agent_nodes as ia
from worker.processor import ejecutar_grafo
from worker.tests.test_worker import lote


def test_error_proveedor_no_se_convierte_en_exito(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'clave-ficticia-prueba')
    def fallo(*args, **kwargs):
        raise requests.Timeout('fallo simulado')
    monkeypatch.setattr(ia.requests, 'post', fallo)
    salida = ejecutar_grafo(lote(), 'openrouter')
    assert salida['errores'] and salida['estado'] != 'completado_local'


@pytest.mark.parametrize('etapa', ['analisis', 'puntuacion'])
def test_respuesta_incompleta_no_inventa_resultados(monkeypatch, etapa):
    monkeypatch.setattr(ia, 'llamar_llm_openrouter', lambda _: {'resultados': []})
    with pytest.raises(ValueError):
        ia.analizar_real(lote()) if etapa == 'analisis' else ia.puntuar_real({'lote': lote()})


def test_json_lista_rechazado(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'clave-ficticia-prueba')
    class Respuesta:
        def raise_for_status(self):
            pass
        def json(self):
            return {'choices': [{'message': {'content': '[]'}}]}
    monkeypatch.setattr(ia.requests, 'post', lambda *a, **kw: Respuesta())
    with pytest.raises(ValueError):
        ia.llamar_llm_openrouter('prueba')
