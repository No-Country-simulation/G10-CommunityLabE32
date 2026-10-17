"""Ciclo independiente de PostgreSQL. La reserva pertenece al adaptador de cola."""
from dataclasses import dataclass
from typing import Callable, Protocol

from pipelines.communitylab.diagnostico import normalizar_diagnostico


@dataclass(frozen=True)
class Trabajo:
    id: str
    token: str
    entrada: dict


class ReservaPerdida(Exception):
    pass


class ProcesamientoFallido(Exception):
    """Código controlado, sin texto del lote ni secretos."""

    def __init__(self, codigo, diagnostico=None):
        super().__init__(codigo)
        self.diagnostico = normalizar_diagnostico(diagnostico)  # solo valores de catálogo, o None


# Errores de IA del grafo (pipelines.communitylab.gemini) traducidos a códigos persistibles.
CODIGOS_IA = {"ia_configuracion", "ia_cuota", "ia_transitorio", "ia_respuesta_invalida",
              "ia_bloqueado", "ia_presupuesto"}
_CODIGO_POR_ERROR = {
    "ErrorConfiguracionIA": "ia_configuracion", "ErrorCuotaIA": "ia_cuota",
    "ErrorTransitorioIA": "ia_transitorio", "RespuestaInvalidaIA": "ia_respuesta_invalida",
    "ContenidoBloqueadoIA": "ia_bloqueado", "PresupuestoAgotadoIA": "ia_presupuesto",
}
CODIGOS = {"fallo_grafo", "contrato_resultado", "timeout", "fallo_procesador"} | CODIGOS_IA


def codigo_de_errores(errores):
    """Primer error de IA reconocido en la salida del grafo, o fallo_grafo."""
    for error in errores or []:
        codigo = _CODIGO_POR_ERROR.get(error.get("tipo")) if isinstance(error, dict) else None
        if codigo:
            return codigo
    return "fallo_grafo"


def diagnostico_de_errores(errores):
    """Diagnóstico normalizado del primer error que lo traiga (ver pipelines.communitylab.diagnostico)."""
    for error in errores or []:
        if isinstance(error, dict) and isinstance(error.get("diagnostico"), dict):
            return normalizar_diagnostico(error["diagnostico"])
    return None


class Cola(Protocol):
    def reservar(self) -> Trabajo | None: ...
    def renovar(self, trabajo: Trabajo) -> bool: ...
    def terminar(self, trabajo: Trabajo, resultado: dict) -> bool: ...
    def fallar(self, trabajo: Trabajo, codigo: str) -> bool: ...


class Worker:
    def __init__(self, cola: Cola, procesador: Callable, latido=lambda: None):
        self.cola = cola
        self.procesador = procesador
        self.latido = latido

    def ejecutar_uno(self) -> bool:
        trabajo = self.cola.reservar()
        self.latido()
        if trabajo is None:
            return False

        def renovar():
            if not self.cola.renovar(trabajo):
                raise ReservaPerdida()
            self.latido()

        try:
            resultado = self.procesador(trabajo.entrada, renovar)
            if not isinstance(resultado, dict):
                raise ProcesamientoFallido("fallo_grafo")
            if resultado.get("estado") != "completado_local":
                raise ProcesamientoFallido(codigo_de_errores(resultado.get("errores")),
                                           diagnostico_de_errores(resultado.get("errores")))
            if type(resultado.get("simulado")) is not bool:
                raise ProcesamientoFallido("contrato_resultado")
            if resultado.get("errores"):
                raise ProcesamientoFallido(codigo_de_errores(resultado["errores"]),
                                           diagnostico_de_errores(resultado["errores"]))
        except ReservaPerdida:
            return True  # Otro intento posee el trabajo; nunca sobrescribirlo.
        except ProcesamientoFallido as exc:
            codigo = str(exc)
            if codigo not in CODIGOS:
                codigo = "fallo_procesador"
            diagnostico = getattr(exc, "diagnostico", None)
            if diagnostico:
                self.cola.fallar(trabajo, codigo, diagnostico=diagnostico)
            else:
                self.cola.fallar(trabajo, codigo)
        except Exception:
            self.cola.fallar(trabajo, "fallo_procesador")
        else:
            # Si falla la persistencia, se conserva la reserva para recuperación.
            self.cola.terminar(trabajo, resultado)
        self.latido()
        return True
