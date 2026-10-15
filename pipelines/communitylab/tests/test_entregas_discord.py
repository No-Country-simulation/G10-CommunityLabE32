import json
from pathlib import Path
import tempfile
import unittest

from pipelines.communitylab.entregas_discord import Entregas
from pipelines.communitylab.normalizador_discord import construir_lotes


def mensaje(n):
    return dict(id=str(n), autor='a', canal='c', fecha='2026-10-14T12:00:00+00:00', texto='Prueba')


class PruebasEntregas(unittest.TestCase):
    def test_reabrir_conserva_lotes_parciales_y_no_reagrupa_al_crecer(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp)/'estado.db'
            a = Entregas(ruta)
            anterior = a.preparar('http://local', [mensaje(n) for n in range(501)], 'discord', 'S3', False, construir_lotes)
            a.confirmar(anterior[0]['clave'], 'trabajo-1', 'terminado')
            nuevo = Entregas(ruta).preparar('http://local', [mensaje(n) for n in range(502)], 'discord', 'S3', False, construir_lotes)
            self.assertEqual([len(json.loads(e['payload'])['interacciones']) for e in nuevo], [500, 1, 1])
            self.assertEqual(nuevo[0]['estado'], 'terminado')
            self.assertEqual(nuevo[1]['clave'], anterior[1]['clave'])
            self.assertEqual(nuevo[1]['payload'], anterior[1]['payload'])

    def test_destinos_independientes_y_contenido_modificado_rechazado(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Entregas(Path(tmp)/'estado.db')
            primera = a.preparar('http://uno', [mensaje(1)], 'discord', 'S3', False, construir_lotes)
            segunda = a.preparar('http://dos', [mensaje(1)], 'discord', 'S3', False, construir_lotes)
            self.assertNotEqual(primera[0]['clave'], segunda[0]['clave'])
            cambiado = {**mensaje(1), 'texto': 'otro texto'}
            with self.assertRaises(ValueError):
                a.preparar('http://uno', [cambiado], 'discord', 'S3', False, construir_lotes)

    def test_cierre_inmutable_no_repite_consolidacion(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Entregas(Path(tmp)/'estado.db')
            a.preparar('http://uno', [mensaje(1)], 'discord', 'S3', True, construir_lotes)
            with self.assertRaises(ValueError):
                a.preparar('http://uno', [mensaje(1), mensaje(2)], 'discord', 'S3', True, construir_lotes)
            with self.assertRaises(ValueError):
                a.preparar('http://uno', [mensaje(1)], 'discord', 'S3', False, construir_lotes)
