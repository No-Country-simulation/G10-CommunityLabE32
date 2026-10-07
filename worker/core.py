"""Ciclo independiente de PostgreSQL. La reserva pertenece al adaptador de cola."""
from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass(frozen=True)
class Trabajo:
    id: str
    token: str
    entrada: dict


class ReservaPerdida(Exception):
    pass


class ProcesamientoFallido(Exception):
    """Código controlado, sin texto del lote ni secretos."""


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
            if not isinstance(resultado, dict) or resultado.get("estado") != "completado_local":
                raise ProcesamientoFallido("fallo_grafo")
            if type(resultado.get("simulado")) is not bool:
                raise ProcesamientoFallido("contrato_resultado")
            if resultado.get("errores"):
                raise ProcesamientoFallido("fallo_grafo")
        except ReservaPerdida:
            return True  # Otro intento posee el trabajo; nunca sobrescribirlo.
        except ProcesamientoFallido as exc:
            codigo = str(exc)
            if codigo not in {"fallo_grafo", "contrato_resultado", "timeout", "fallo_procesador"}:
                codigo = "fallo_procesador"
            self.cola.fallar(trabajo, codigo)
        except Exception:
            self.cola.fallar(trabajo, "fallo_procesador")
        else:
            # Si falla la persistencia, se conserva la reserva para recuperación.
            self.cola.terminar(trabajo, resultado)
        self.latido()
        return True
