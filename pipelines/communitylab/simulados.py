"""Dobles deterministas de prueba. No implementan análisis ni generación con IA."""
from copy import deepcopy
from .grafo import Componentes


def crear_componentes(señales):
    referencia = deepcopy(señales)

    def analizar(lote):
        return {m["id"]: {k: v for k, v in referencia[m["id"]].items() if k != "relevancia"}
                for m in lote["interacciones"]}

    def puntuar(peticion):
        return {m["id"]: referencia[m["id"]]["relevancia"] for m in peticion["lote"]["interacciones"]}

    def generar(peticion):
        return {"copy": f"[SIMULADO — NO PUBLICAR] {peticion['formato']}: " + ", ".join(peticion["fuentes"]),
                "fuentes": deepcopy(peticion["fuentes"])}

    return Componentes(analizar, puntuar, generar, generar, generar, simulado=True)
