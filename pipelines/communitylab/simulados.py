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
        fuentes_str = []
        for id_f in peticion["fuentes"]:
            # Buscamos el autor en las interacciones
            autor = "AutorDesconocido"
            for inter in peticion["interacciones"]:
                if inter["id"] == id_f:
                    autor = inter.get("autor", "AutorDesconocido")
                    break
            fuentes_str.append(f"[Fuente: {autor} - {id_f}]")
            
        citas = "\n".join(fuentes_str)
        return {
            "copy": f"[SIMULADO — NO PUBLICAR] {peticion['formato']} generado a partir de fuentes.\n\n{citas}",
            "fuentes": deepcopy(peticion["fuentes"])
        }

    return Componentes(analizar, puntuar, generar, generar, generar, simulado=True)
