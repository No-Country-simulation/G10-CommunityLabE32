"""Instancia única y salud del lector como servicio (sin Discord)."""
import asyncio
from pathlib import Path
import tempfile
import unittest

from discord_reader.servicio import escribir_latido, instance_lock, latido_sano, latir


class PruebasServicio(unittest.TestCase):
    def test_segunda_instancia_sobre_la_misma_bandeja_falla(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "discord.sqlite3"
            with instance_lock(base):
                with self.assertRaises((BlockingIOError, PermissionError, OSError)):
                    with instance_lock(base):
                        pass
            with instance_lock(base):  # liberado al terminar
                pass

    def test_salud_por_latido_y_conexion(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "latido.json"
            self.assertFalse(latido_sano(ruta))
            escribir_latido(ruta, True, None, reloj=lambda: 1000)
            # Conectado y sin mensajes recientes: sano (un canal tranquilo no es una falla).
            self.assertTrue(latido_sano(ruta, reloj=lambda: 1030))
            self.assertFalse(latido_sano(ruta, maximo_latido=60, reloj=lambda: 1100))
            escribir_latido(ruta, False, 900, reloj=lambda: 1000)
            self.assertTrue(latido_sano(ruta, maximo_desconexion=600, reloj=lambda: 1010))
            escribir_latido(ruta, False, 100, reloj=lambda: 1000)
            self.assertFalse(latido_sano(ruta, maximo_desconexion=600, reloj=lambda: 1010))

    def test_latir_refleja_el_estado_de_la_sesion(self):
        class Cliente:
            channels_verified = False

        async def correr(ruta):
            tarea = asyncio.create_task(latir(Cliente(), ruta, reloj=lambda: 50, intervalo=0.01))
            await asyncio.sleep(0.05)
            Cliente.channels_verified = True
            await asyncio.sleep(0.05)
            tarea.cancel()
            await asyncio.gather(tarea, return_exceptions=True)

        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "latido.json"
            asyncio.run(correr(ruta))
            self.assertIn('"conectado": true', ruta.read_text())


if __name__ == "__main__":
    unittest.main()
