"""Salud del bot como servicio: latido, sesión verificada y comando `salud`."""
from pathlib import Path
import tempfile
import unittest

from bot_discord.__main__ import main
from bot_discord import servicio

RAIZ = Path(__file__).resolve().parents[2]  # integrations/discord


class PruebasServicioBot(unittest.TestCase):
    def test_comando_salud(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "latido.json"
            self.assertEqual(main(["salud", "--latido", str(ruta)]), 1)
            servicio.escribir_latido(ruta, True, None)
            self.assertEqual(main(["salud", "--latido", str(ruta)]), 0)

    def test_misma_implementacion_que_el_lector(self):
        # Copia deliberada (paquetes independientes); deben mantenerse idénticas.
        lector = (RAIZ / "reader" / "discord_reader" / "servicio.py").read_text(encoding="utf-8")
        self.assertEqual((RAIZ / "bot" / "bot_discord" / "servicio.py").read_text(encoding="utf-8"), lector)


if __name__ == "__main__":
    unittest.main()
