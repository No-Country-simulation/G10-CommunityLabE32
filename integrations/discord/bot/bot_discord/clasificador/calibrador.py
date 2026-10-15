"""
calibrador.py — Calibración OFFLINE de config_clasificador.json (SOLO LECTURA).

Qué hace
    Mide el clasificador con un conjunto etiquetado y PROPONE valores para los umbrales,
    márgenes, temperaturas y pesos de la configuración. Nunca escribe la configuración:
      * trabaja sobre una copia en memoria (copy.deepcopy);
      * jamás llama a agregar_prototipo(persistir=True) ni toca correcciones.jsonl;
      * el único archivo que puede escribir es --salida (un reporte aparte), y se rechaza
        si apunta al config, al dataset o al archivo de correcciones;
      * al final verifica por hash que el config quedó byte a byte idéntico.
    Los cambios se aplican a mano (o con tu propio proceso) a partir del reporte.

Cómo evalúa
    Reutiliza ClasificadorInteracciones.decidir() de producción (no duplica la lógica) con
    registrar=False (sin contexto ni efectos secundarios). La similitud con los prototipos se
    recalcula con leave-one-out: si el texto evaluado es también un prototipo (mismo texto
    normalizado), ese prototipo se excluye, para que no se compare consigo mismo.

Datos
    --dataset datos.jsonl   líneas {"texto": "...", "clase": "LOGRO|DUDA_TECNICA|
                            BLOQUEO_FRUSTRACION|RUIDO|NO_CLASIFICADO"}. Es la opción recomendada.
    (sin --dataset)         arranque: usa los propios prototipos del config (y correcciones)
                            con leave-one-out. Sirve para humo/regresión, NO para decidir
                            valores finales: la muestra es pequeña y optimista.
    RUIDO se evalúa como NO_CLASIFICADO (así lo trata el clasificador y registrar_correccion).

Etapas (--etapas, por defecto clase,revision,confianza; "pesos" es opcional)
    pesos      pesos del combinador de scores      objetivo: F1 macro   (riesgo de sobreajuste)
    clase      umbral[motor], promocion_duda_a_bloqueo   objetivo: F1 macro
    revision   margen_minimo[motor], conflicto_logro_neg, bloqueo_con_pos
               objetivo: F-beta de "necesita_revision" como detector de errores
    confianza  temperatura[motor] (+ factor_confianza_fallback si el motor es fallback)
               objetivo: Brier de `confianza` sobre predicciones de clases objetivo

    Solo se calibran los valores del motor ACTIVO en esta corrida (embeddings o fallback);
    los del otro motor requieren correr el calibrador con ese motor disponible.

Uso
    python calibrador.py --config config_clasificador.json --dataset datos.jsonl
    python calibrador.py --fallback --etapas clase,revision --salida reporte_calibracion.json
    python calibrador.py --dataset dataset_ejemplo.jsonl --etapas clase,revision --salida reporte_calibracion.json
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from classifier import (
    BLOQUEO_FRUSTRACION, CLASES_OBJETIVO, DUDA_TECNICA, LOGRO, NO_CLASIFICADO, RUIDO,
    RUTA_CONFIG_DEFECTO, SCHEMA_ENTRADA, ClasificacionResultado, ClasificadorInteracciones,
    DiscordSourceV1, _Analisis, _normalizar, cargar_config,
)

CLASES_SALIDA = (LOGRO, DUDA_TECNICA, BLOQUEO_FRUSTRACION, NO_CLASIFICADO)
ETAPAS = ("pesos", "clase", "revision", "confianza")
ETAPAS_DEFECTO = ("clase", "revision", "confianza")
# Mejora mínima del objetivo para aceptar un cambio (evita perseguir ruido de muestra chica).
MIN_MEJORA = {"pesos": 0.02, "clase": 0.01, "revision": 0.01, "confianza": 0.002}
MUESTRA_MIN_POR_CLASE = 30
ABREV = {LOGRO: "LOGRO", DUDA_TECNICA: "DUDA", BLOQUEO_FRUSTRACION: "BLOQ", NO_CLASIFICADO: "N/C"}


# --------------------------------------------------------------------------- #
# Datos
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Ejemplo:
    texto: str
    gold: str  # ya mapeado: RUIDO -> NO_CLASIFICADO


def _gold(clase: str) -> str:
    return NO_CLASIFICADO if clase == RUIDO else clase


def cargar_dataset(ruta: Path) -> List[Ejemplo]:
    out: List[Ejemplo] = []
    for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
        if not linea.strip():
            continue
        try:
            reg = json.loads(linea)
            texto, clase = reg["texto"], _gold(reg["clase"])
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ValueError(f"{ruta}:{n}: línea inválida ({exc!r})") from exc
        if not isinstance(texto, str) or clase not in CLASES_SALIDA:
            raise ValueError(f"{ruta}:{n}: texto/clase inválidos (clase={reg.get('clase')!r})")
        out.append(Ejemplo(texto, clase))
    if not out:
        raise ValueError(f"{ruta}: dataset vacío")
    return out


def dataset_desde_prototipos(clf: ClasificadorInteracciones) -> List[Ejemplo]:
    return [Ejemplo(t, _gold(c)) for c, textos in clf.motor.prototipos.items() for t in textos]


# --------------------------------------------------------------------------- #
# Métricas
# --------------------------------------------------------------------------- #
def _f1_clase(gold: Sequence[str], pred: Sequence[str], c: str) -> float:
    tp = sum(g == c and p == c for g, p in zip(gold, pred))
    fp = sum(g != c and p == c for g, p in zip(gold, pred))
    fn = sum(g == c and p != c for g, p in zip(gold, pred))
    pr = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    return 2 * pr * rc / (pr + rc) if pr + rc else 0.0


def f1_macro(gold: Sequence[str], pred: Sequence[str]) -> float:
    presentes = [c for c in CLASES_SALIDA if c in set(gold) or c in set(pred)]
    return float(np.mean([_f1_clase(gold, pred, c) for c in presentes])) if presentes else 0.0


def f_revision(gold: Sequence[str], res: Sequence[ClasificacionResultado], beta: float) -> float:
    """F-beta de `necesita_revision` como detector de errores. Sin errores: -tasa de revisión."""
    err = [r.clase != g for r, g in zip(res, gold)]
    flag = [r.necesita_revision for r in res]
    if not any(err):
        return -sum(flag) / len(flag)
    tp = sum(e and f for e, f in zip(err, flag))
    fp = sum((not e) and f for e, f in zip(err, flag))
    fn = sum(e and (not f) for e, f in zip(err, flag))
    pr = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    b2 = beta * beta
    return (1 + b2) * pr * rc / (b2 * pr + rc) if (b2 * pr + rc) else 0.0


def calibracion(gold: Sequence[str], res: Sequence[ClasificacionResultado], bins: int = 5
                ) -> Tuple[float, float, int]:
    """(Brier, ECE, n) de `confianza` solo sobre predicciones de clases objetivo (las que responden)."""
    pares = [(r.confianza, float(r.clase == g)) for r, g in zip(res, gold) if r.clase in CLASES_OBJETIVO]
    if not pares:
        return float("nan"), float("nan"), 0
    conf = np.array([p[0] for p in pares])
    ok = np.array([p[1] for p in pares])
    brier = float(np.mean((conf - ok) ** 2))
    bordes = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for i in range(bins):
        m = (conf >= bordes[i]) & ((conf < bordes[i + 1]) if i < bins - 1 else (conf <= bordes[i + 1]))
        if m.any():
            ece += m.mean() * abs(conf[m].mean() - ok[m].mean())
    return brier, float(ece), len(pares)


def matriz_confusion(gold: Sequence[str], pred: Sequence[str]) -> Dict[str, Dict[str, int]]:
    m = {g: {p: 0 for p in CLASES_SALIDA} for g in CLASES_SALIDA}
    for g, p in zip(gold, pred):
        m[g][p if p in CLASES_SALIDA else NO_CLASIFICADO] += 1
    return m


# --------------------------------------------------------------------------- #
# Evaluador (reusa decidir() de producción)
# --------------------------------------------------------------------------- #
class Evaluador:
    def __init__(self, clf: ClasificadorInteracciones, ejemplos: Sequence[Ejemplo]) -> None:
        self.clf = clf
        self.ejemplos = list(ejemplos)
        self.gold = [e.gold for e in self.ejemplos]
        self.analisis = self._preparar()

    def _preparar(self) -> List[_Analisis]:
        clf, motor = self.clf, self.clf.motor
        sans = [clf.sanitizador.limpiar(e.texto) for e in self.ejemplos]
        textos = [s.texto for s in sans]
        X = motor.codificar(textos)
        mats = {c: motor.codificar(motor.prototipos[c]) for c in motor.clases}
        norm = {c: np.array([_normalizar(t) for t in motor.prototipos[c]]) for c in motor.clases}
        sents = clf.sentimiento.analizar_lote(textos)
        ahora = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()
        out: List[_Analisis] = []
        for i, (e, san) in enumerate(zip(self.ejemplos, sans)):
            clave = _normalizar(e.texto)
            fila: List[float] = []
            for c in motor.clases:
                cos = X[i] @ mats[c].T
                cos = cos[norm[c] != clave]  # leave-one-out por texto
                if cos.size == 0:
                    fila.append(0.0)
                    continue
                k = min(motor.k, cos.size)
                fila.append(float(np.sort(cos)[-k:].mean()))
            fuente = DiscordSourceV1(SCHEMA_ENTRADA, f"cal-{i}", "cal", "cal", f"autor-{i}", ahora, e.texto)
            corto = len(san.texto) < clf.longitud_minima
            out.append(_Analisis(fuente, san, san.texto, False, corto, np.array(fila), sents[i]))
        return out

    def correr(self) -> List[ClasificacionResultado]:
        return [self.clf.decidir(a, registrar=False) for a in self.analisis]


def metricas(ev: Evaluador, beta: float) -> Dict[str, Any]:
    res = ev.correr()
    pred = [r.clase for r in res]
    brier, ece, n_conf = calibracion(ev.gold, res)
    return {
        "n": len(pred),
        "exactitud": float(np.mean([g == p for g, p in zip(ev.gold, pred)])),
        "f1_macro": f1_macro(ev.gold, pred),
        "f1_por_clase": {c: _f1_clase(ev.gold, pred, c) for c in CLASES_SALIDA},
        "tasa_revision": float(np.mean([r.necesita_revision for r in res])),
        "f_revision": f_revision(ev.gold, res, beta),
        "brier": brier, "ece": ece, "n_confianza": n_conf,
        "confusion": matriz_confusion(ev.gold, pred),
    }


# --------------------------------------------------------------------------- #
# Parámetros ajustables (solo sobre la copia en memoria)
# --------------------------------------------------------------------------- #
@dataclass
class Parametro:
    nombre: str
    ruta: Tuple[str, ...]            # ruta dentro del JSON de config (para el parche)
    leer: Callable[[], float]
    escribir: Callable[[float], None]
    rejilla: List[float]
    original: float = 0.0


def _rej(lo: float, hi: float, paso: float) -> List[float]:
    return [round(float(x), 4) for x in np.arange(lo, hi + paso / 2, paso)]


def construir_parametros(clf: ClasificadorInteracciones) -> Dict[str, Parametro]:
    m = clf.motor.motor
    P: Dict[str, Parametro] = {}

    def attr(nombre: str, ruta: Tuple[str, ...], atributo: str, rejilla: List[float]) -> None:
        P[nombre] = Parametro(nombre, ruta, lambda: getattr(clf, atributo),
                              lambda v: setattr(clf, atributo, v), rejilla)

    def dic(nombre: str, ruta: Tuple[str, ...], d: Dict[str, Any], clave: str, rejilla: List[float]) -> None:
        P[nombre] = Parametro(nombre, ruta, lambda: d[clave], lambda v: d.__setitem__(clave, v), rejilla)

    attr(f"umbral[{m}]", ("umbral", m), "umbral", _rej(0.02, 0.60, 0.01))
    attr(f"margen_minimo[{m}]", ("margen_minimo", m), "margen", _rej(0.0, 0.20, 0.005))
    attr(f"temperatura[{m}]", ("temperatura", m), "temperatura", _rej(0.02, 0.30, 0.01))
    clf.config.setdefault("factor_confianza_fallback", 0.6)  # solo la copia en memoria
    dic("factor_confianza_fallback", ("factor_confianza_fallback",), clf.config,
        "factor_confianza_fallback", _rej(0.30, 1.00, 0.05))
    for k in ("promocion_duda_a_bloqueo", "conflicto_logro_neg", "bloqueo_con_pos"):
        dic(f"sentimiento:{k}", ("sentimiento", k), clf.sent_cfg, k, _rej(0.30, 0.95, 0.05))
    for k, v in clf.pesos.items():
        base = float(v)
        rej = sorted({round(base * f, 4) for f in (0, 0.5, 0.75, 1, 1.25, 1.5, 2)}) if base > 0 \
            else _rej(0.0, 0.10, 0.02)
        dic(f"peso:{k}", ("pesos", k), clf.pesos, k, rej)
    for p in P.values():
        p.original = p.leer()
    return P


# --------------------------------------------------------------------------- #
# Búsqueda: barrido por parámetro + descenso coordenado
# --------------------------------------------------------------------------- #
def barrer(p: Parametro, objetivo: Callable[[], float], min_mejora: float) -> Dict[str, Any]:
    """Barre la rejilla, elige el centro de la mejor meseta (promedio de 3 vecinos) y solo
    acepta el cambio si mejora el objetivo al menos `min_mejora` sobre el valor actual."""
    actual = p.leer()
    base = objetivo()
    vals = p.rejilla
    puntos: List[float] = []
    for v in vals:
        p.escribir(v)
        puntos.append(objetivo())
    p.escribir(actual)
    suav = [float(np.mean(puntos[max(0, i - 1):i + 2])) for i in range(len(vals))]
    i_mejor = max(range(len(vals)), key=lambda i: (round(suav[i], 9), -abs(vals[i] - actual)))
    aceptado = puntos[i_mejor] - base >= min_mejora
    if aceptado:
        p.escribir(vals[i_mejor])
    mejor_raw = max(puntos)
    meseta = [v for v, s in zip(vals, puntos) if s >= mejor_raw - 0.005]
    return {"base": base, "mejor_raw": mejor_raw, "elegido": p.leer(), "aceptado": aceptado,
            "meseta": [min(meseta), max(meseta)]}


def descenso(P: Dict[str, Parametro], nombres: Sequence[str], objetivo: Callable[[], float],
             min_mejora: float, pasadas: int) -> Dict[str, Dict[str, Any]]:
    info: Dict[str, Dict[str, Any]] = {}
    for _ in range(max(1, pasadas)):
        hubo_cambio = False
        for n in nombres:
            antes = P[n].leer()
            info[n] = barrer(P[n], objetivo, min_mejora)
            hubo_cambio |= P[n].leer() != antes
        if not hubo_cambio:
            break
    return info


def calibrar(clf: ClasificadorInteracciones, ev: Evaluador, etapas: Sequence[str], beta: float,
             pasadas: int) -> Tuple[Dict[str, Parametro], Dict[str, Dict[str, Any]]]:
    P = construir_parametros(clf)
    m = clf.motor.motor
    obj_clase = lambda: f1_macro(ev.gold, [r.clase for r in ev.correr()])  # noqa: E731
    obj_rev = lambda: f_revision(ev.gold, ev.correr(), beta)  # noqa: E731
    obj_conf = lambda: -calibracion(ev.gold, ev.correr())[0]  # noqa: E731
    plan = {
        "pesos": ([n for n in P if n.startswith("peso:")], obj_clase),
        "clase": ([f"umbral[{m}]", "sentimiento:promocion_duda_a_bloqueo"], obj_clase),
        "revision": ([f"margen_minimo[{m}]", "sentimiento:conflicto_logro_neg",
                      "sentimiento:bloqueo_con_pos"], obj_rev),
        "confianza": ([f"temperatura[{m}]"] + (["factor_confianza_fallback"] if m == "fallback" else []),
                      obj_conf),
    }
    curvas: Dict[str, Dict[str, Any]] = {}
    for etapa in ETAPAS:  # orden fijo: lo que cambia clases va antes que revisión y confianza
        if etapa in etapas:
            nombres, objetivo = plan[etapa]
            curvas.update(descenso(P, nombres, objetivo, MIN_MEJORA[etapa], pasadas))
    return P, curvas


# --------------------------------------------------------------------------- #
# Reporte
# --------------------------------------------------------------------------- #
def _fmt(x: float) -> str:
    return "n/d" if x != x else f"{x:.3f}"


def _parche(P: Dict[str, Parametro]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for p in P.values():
        nuevo = p.leer()
        if nuevo != p.original:
            d = out
            for k in p.ruta[:-1]:
                d = d.setdefault(k, {})
            d[p.ruta[-1]] = nuevo
    return out


def imprimir_reporte(clf: ClasificadorInteracciones, fuente_datos: str, ejemplos: Sequence[Ejemplo],
                     antes: Dict[str, Any], despues: Dict[str, Any], P: Dict[str, Parametro],
                     curvas: Dict[str, Dict[str, Any]], beta: float, etapas: Sequence[str]) -> List[str]:
    adv: List[str] = []
    dist = {c: sum(e.gold == c for e in ejemplos) for c in CLASES_SALIDA}
    if fuente_datos == "prototipos":
        adv.append("Muestra de arranque (prototipos con leave-one-out): sirve para humo/regresión, "
                   "no para fijar valores finales. Usa --dataset con mensajes reales etiquetados.")
    chicas = [ABREV[c] for c, n in dist.items() if n < MUESTRA_MIN_POR_CLASE]
    if chicas:
        adv.append(f"Menos de {MUESTRA_MIN_POR_CLASE} ejemplos en {', '.join(chicas)}: "
                   "las diferencias pequeñas son ruido; revisa la meseta de cada parámetro.")
    if clf.motor.motor == "fallback":
        adv.append("Motor FALLBACK: los valores propuestos no aplican al motor 'embeddings'.")
    if "pesos" in etapas:
        adv.append("Etapa 'pesos' activa: alto riesgo de sobreajuste con muestras chicas.")

    print("== Calibración de config_clasificador.json (SOLO LECTURA: no se modificó nada) ==")
    print(f"Motor: {clf.motor.motor} | Sentimiento: {clf.sentimiento.motor} | "
          f"Muestra: {len(ejemplos)} (fuente: {fuente_datos}) | Etapas: {', '.join(etapas)}")
    print("Distribución: " + " · ".join(f"{ABREV[c]} {n}" for c, n in dist.items()))
    for a in adv:
        print(f"  ! {a}")

    print("\n-- Métricas (antes -> después) --")
    filas = [("exactitud", "exactitud"), ("F1 macro", "f1_macro"),
             (f"F{beta:g} de revisión", "f_revision"), ("tasa de revisión", "tasa_revision"),
             ("Brier (menor=mejor)", "brier"), ("ECE (menor=mejor)", "ece")]
    for etiqueta, k in filas:
        print(f"  {etiqueta:<22} {_fmt(antes[k])} -> {_fmt(despues[k])}")
    for c in CLASES_SALIDA:
        print(f"  F1 {ABREV[c]:<19} {_fmt(antes['f1_por_clase'][c])} -> {_fmt(despues['f1_por_clase'][c])}")

    print("\n-- Cambios propuestos (para aplicar manualmente) --")
    cambios = [p for p in P.values() if p.leer() != p.original]
    if not cambios:
        print("  Ninguno: ningún cambio superó la mejora mínima exigida.")
    for p in cambios:
        meseta = curvas.get(p.nombre, {}).get("meseta")
        extra = f"   meseta≈[{meseta[0]}, {meseta[1]}]" if meseta else ""
        if p.leer() in (p.rejilla[0], p.rejilla[-1]):
            extra += "   ¡en el borde de la rejilla: el óptimo podría estar fuera!"
            adv.append(f"{p.nombre} quedó en el borde de la rejilla ({p.leer()}); "
                       "amplía el rango o revisa con más datos.")
        print(f"  {p.nombre:<40} {p.original} -> {p.leer()}{extra}")

    print("\n-- Matriz de confusión después (filas=real, columnas=predicho) --")
    print("  " + " " * 6 + "".join(f"{ABREV[c]:>6}" for c in CLASES_SALIDA))
    for g in CLASES_SALIDA:
        print(f"  {ABREV[g]:<6}" + "".join(f"{despues['confusion'][g][p]:>6}" for p in CLASES_SALIDA))
    return adv


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _sha(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Calibrador (solo lectura) de config_clasificador.json")
    ap.add_argument("--config", default=str(RUTA_CONFIG_DEFECTO))
    ap.add_argument("--dataset", help="JSONL con {'texto','clase'}; sin él se usan los prototipos")
    ap.add_argument("--etapas", default=",".join(ETAPAS_DEFECTO), help=f"subconjunto de {ETAPAS}")
    ap.add_argument("--fallback", action="store_true", help="forzar motor/sentimiento de respaldo")
    ap.add_argument("--beta", type=float, default=1.0, help="beta del F-beta de revisión (>1 prioriza recall)")
    ap.add_argument("--pasadas", type=int, default=2, help="pasadas del descenso coordenado")
    ap.add_argument("--salida", help="reporte JSON (nunca el config/dataset/correcciones)")
    args = ap.parse_args(argv)

    etapas = [e.strip() for e in args.etapas.split(",") if e.strip()]
    invalidas = [e for e in etapas if e not in ETAPAS]
    if invalidas:
        ap.error(f"etapas inválidas: {invalidas}; válidas: {list(ETAPAS)}")

    ruta = Path(args.config)
    hash_antes = _sha(ruta)
    cfg = cargar_config(ruta)
    clf = ClasificadorInteracciones(ruta_config=ruta, config=copy.deepcopy(cfg),
                                    forzar_fallback=args.fallback)

    protegidos = {ruta.resolve()}
    if args.dataset:
        protegidos.add(Path(args.dataset).resolve())
    if clf.motor.ruta_correcciones:
        protegidos.add(Path(clf.motor.ruta_correcciones).resolve())
    if args.salida and Path(args.salida).resolve() in protegidos:
        ap.error("--salida apunta a un archivo protegido (config, dataset o correcciones)")

    if args.dataset:
        try:
            ejemplos, fuente_datos = cargar_dataset(Path(args.dataset)), "dataset"
        except (OSError, ValueError) as exc:
            ap.error(f"dataset inválido: {exc}")
    else:
        ejemplos, fuente_datos = dataset_desde_prototipos(clf), "prototipos"

    ev = Evaluador(clf, ejemplos)
    antes = metricas(ev, args.beta)
    P, curvas = calibrar(clf, ev, etapas, args.beta, args.pasadas)
    despues = metricas(ev, args.beta)
    adv = imprimir_reporte(clf, fuente_datos, ejemplos, antes, despues, P, curvas, args.beta, etapas)

    if _sha(ruta) != hash_antes:  # defensa en profundidad; no debería ocurrir jamás
        print("ERROR: el config cambió durante la calibración.", file=sys.stderr)
        return 2
    print("\nConfig verificado: sin cambios (hash idéntico).")

    if args.salida:
        reporte = {
            "generado": datetime.now(timezone.utc).isoformat(),
            "motor": clf.motor.motor, "sentimiento": clf.sentimiento.motor,
            "fuente_datos": fuente_datos, "n": len(ejemplos), "etapas": etapas,
            "advertencias": adv, "metricas_antes": antes, "metricas_despues": despues,
            "parche_sugerido": _parche(P), "curvas": curvas,
        }
        Path(args.salida).write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Reporte escrito en {args.salida} (el config NO fue tocado).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
