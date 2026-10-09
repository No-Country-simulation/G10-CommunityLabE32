"""Ejecución aislada del grafo: tiempo límite y renovación de reserva."""
import multiprocessing as mp
import os
import time

from worker.core import ProcesamientoFallido


def ejecutar_grafo(entrada, modo):
    from pipelines.communitylab import Componentes, ejecutar_lote
    if modo == "simulado":
        from pipelines.communitylab.simulados import crear_componentes
        # Señales explícitas de demostración, nunca inferencias presentadas como IA.
        senales = {
            m["id"]: {"es_logro": m.get("tipo") == "logro",
                      "es_duda": m.get("tipo") == "duda",
                      "es_bloqueo": m.get("tipo") == "bloqueo",
                      "tema": m["canal"], "relevancia": 0.8}
            for m in entrada["interacciones"]
        }
        componentes = crear_componentes(senales)
    elif modo == "openrouter":
        if not os.environ.get("OPENROUTER_API_KEY"):
            raise ValueError("Falta configurar OpenRouter")
        from backend.app.pipelines.agent_nodes import (
            analizar_real, puntuar_real, post_real, faq_real, highlights_real,
        )
        componentes = Componentes(analizar_real, puntuar_real, post_real,
                                 faq_real, highlights_real, simulado=False)
    else:
        raise ValueError("Modo de procesamiento inválido")
    return ejecutar_lote(entrada, componentes)


def _hijo(conexion, entrada, modo):
    try:
        conexion.send((True, ejecutar_grafo(entrada, modo)))
    except Exception:
        conexion.send((False, "fallo_procesador"))
    finally:
        conexion.close()


class ProcesadorAislado:
    def __init__(self, modo, timeout=120, renovar_cada=5, detenido=lambda: False,
                 objetivo=_hijo):
        if modo not in {"simulado", "openrouter"} or timeout <= 0 or renovar_cada <= 0:
            raise ValueError("Configuración inválida")
        self.modo, self.timeout, self.renovar_cada = modo, timeout, renovar_cada
        self.detenido, self.objetivo = detenido, objetivo

    def __call__(self, entrada, renovar):
        contexto = mp.get_context("spawn")
        receptor, emisor = contexto.Pipe(duplex=False)
        proceso = contexto.Process(target=self.objetivo, args=(emisor, entrada, self.modo))
        proceso.start()
        emisor.close()
        inicio = ultima = time.monotonic()
        try:
            while True:
                if self.detenido():
                    raise KeyboardInterrupt()  # La reserva se recupera al vencer.
                ahora = time.monotonic()
                if ahora - inicio >= self.timeout:
                    raise ProcesamientoFallido("timeout")
                if ahora - ultima >= self.renovar_cada:
                    renovar()
                    ultima = ahora
                if receptor.poll(0.1):
                    try:
                        ok, resultado = receptor.recv()
                    except EOFError:
                        raise ProcesamientoFallido("fallo_procesador") from None
                    if not ok:
                        raise ProcesamientoFallido("fallo_procesador")
                    return resultado
                if not proceso.is_alive():
                    raise ProcesamientoFallido("fallo_procesador")
        finally:
            if proceso.is_alive():
                proceso.terminate()
            proceso.join(timeout=5)
            if proceso.is_alive():
                proceso.kill()
                proceso.join()
            receptor.close()
