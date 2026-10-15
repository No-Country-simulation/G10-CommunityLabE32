"""
Módulo de integración con el grafo orquestador.
Define la dataclass inmutable 'Componentes', funciones mock para etapas previas
y la factoría de ensamblado de generadores con modelos de IA reales.
"""

from dataclasses import dataclass
from typing import Callable, Dict, Any

from generadores.post_generador import generar_post
from generadores.faq_generador import generar_faq
from generadores.highlights_generador import generar_highlights

# Nota arquitectónica:
# `Componentes` está duplicado en integración y en el grafo.
# Aunque las estructuras sean iguales, Python las considera tipos distintos.
# La definición debería mantenerse en un único lugar (preferiblemente el grafo)
# e importarse desde aquí para evitar fallos de validación por `isinstance()`.

class ContratoInvalido(Exception):
    """Excepción lanzada cuando una estructura o contrato no cumple las especificaciones."""
    pass

@dataclass(frozen=True)
class Componentes:
    """
    Estructura inmutable que transporta las funciones operativas hacia el grafo.
    Garantiza que ningún componente mute el estado global y que cada ranura sea ejecutable.
    """
    analizar: Callable[[Dict[str, Any]], Dict[str, Any]]
    puntuar: Callable[[Dict[str, Any]], Dict[str, Any]]
    generar_post: Callable[[Dict[str, Any]], Dict[str, Any]]
    generar_faq: Callable[[Dict[str, Any]], Dict[str, Any]]
    generar_highlights: Callable[[Dict[str, Any]], Dict[str, Any]]
    simulado: bool

    def __post_init__(self) -> None:
        """
        Validación contractual en tiempo de instanciación.
        Verifica el flag booleano y la naturaleza 'callable' de cada función.
        """
        if type(self.simulado) is not bool:
            raise ContratoInvalido("El atributo 'simulado' debe ser estrictamente de tipo booleano.")

        for nombre in ("analizar", "puntuar", "generar_post", "generar_faq", "generar_highlights"):
            atributo = getattr(self, nombre)
            if not callable(atributo):
                raise ContratoInvalido(f"El componente '{nombre}' debe ser una función ejecutable (Callable).")

def mock_analizar(estado: Dict[str, Any]) -> Dict[str, Any]:
    """
    Doble de prueba pasivo para la etapa de análisis.
    Retorna el estado sin mutaciones para pruebas aisladas de generadores.
    """
    return estado

def mock_puntuar(estado: Dict[str, Any]) -> Dict[str, Any]:
    """
    Doble de prueba pasivo para la etapa de puntuación/scoring.
    Retorna el estado sin mutaciones para pruebas aisladas de generadores.
    """
    return estado

def crear_componentes_reales() -> Componentes:
    """
    Construye e inyecta la instancia productiva/real de Componentes.
    Conecta los tres generadores de IA (Gemini) y define 'simulado=False'.
    """
    return Componentes(
        analizar=mock_analizar,
        puntuar=mock_puntuar,
        generar_post=generar_post,
        generar_faq=generar_faq,
        generar_highlights=generar_highlights,
        simulado=False,
    )

def crear_componentes_simulados() -> Componentes:
    """
    Construye una instancia puramente simulada para pruebas offline o CI/CD.
    Define 'simulado=True' y utiliza funciones dummy sin consumo de cuota de API.
    """
    def dummy_post(peticion: Dict[str, Any]) -> Dict[str, Any]:
        return {"copy": "Post simulado para testing", "fuentes": list(peticion.get("fuentes", []))}

    def dummy_faq(peticion: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "copy": "FAQ: Tema\n\nPregunta: Duda\n\nRespuesta: Solución simulada",
            "fuentes": list(peticion.get("fuentes", [])),
        }

    def dummy_highlights(peticion: Dict[str, Any]) -> Dict[str, Any]:
        return {"copy": "Highlights comunitarios simulados", "fuentes": list(peticion.get("fuentes", []))}

    return Componentes(
        analizar=mock_analizar,
        puntuar=mock_puntuar,
        generar_post=dummy_post,
        generar_faq=dummy_faq,
        generar_highlights=dummy_highlights,
        simulado=True,
    )