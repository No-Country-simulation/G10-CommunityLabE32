# Generadores de activos con Gemini

Prompts y reglas editoriales de **Fabián**; integración con el grafo y el worker. Los tres
generadores (`post_linkedin_x`, `faq_tip_tecnico`, `community_highlights`) se ejecutan dentro
del grafo real (`pipelines.communitylab`) con la clase `Componentes` canónica. Política de
modelos, plazos y presupuesto: [docs/gemini-grafo-worker.md](../../../docs/gemini-grafo-worker.md).

## Estructura

| Archivo | Contenido |
|---|---|
| `prompts/` | Prompts de sistema y formateadores de usuario de Fabián (sin cambios de contenido). |
| `contrato.py` | Validación de la petición del grafo y de la salida `{'copy', 'fuentes'}` (antes `router_generador.py`). |
| `post_generador.py`, `faq_generador.py`, `highlights_generador.py` | Un generador por formato. |
| `_comun.py` | Llamada estructurada a Gemini (`{"copy": ...}`), limpieza y validación local. |

Se retiraron del prototipo: `config.py` (SDK `google-genai` y `load_dotenv`), la `Componentes`
duplicada con análisis/puntuación ficticios, `test.py` (llamaba a Gemini y escribía archivos),
las salidas `salida_*.json` y el `requirements.txt` en UTF-16. Las dependencias usadas
(`httpx`) ya están en `pipelines/communitylab/requirements*.txt`.

## Contrato

Entrada: la petición que arma el grafo para el destino elegido por el router.

```json
{"ruta": "dudas", "formato": "faq_tip_tecnico", "origen_comunidad": "...", "periodo_referencia": "...",
 "fuentes": ["m003", "m004"],
 "interacciones": [{"id": "m003", "autor": "...", "canal": "...", "fecha": "...", "texto": "..."}]}
```

- `fuentes` y los `id` de `interacciones` deben coincidir exactamente, sin duplicados ni IDs ajenos.
- Textos no vacíos y con límites de tamaño; el formato debe corresponder al generador.
- Una petición inválida se rechaza antes de llamar a Gemini.

Salida: `{"copy": "texto no vacío", "fuentes": [...]}` con exactamente las fuentes recibidas.
El modelo solo redacta el `copy`; nunca decide las fuentes.

## Catálogo de Formatos Generativos y Reglas de Negocio

```
┌────────────────────────────────────────────────────────────────────────┐
│                   CATÁLOGO DE AGENTES GENERADORES                      │
├──────────────────────┬──────────────────────┬──────────────────────────┤
│ Formato              │ Entrada Clave        │ Salida Estructurada      │
├──────────────────────┼──────────────────────┼──────────────────────────┤
│ post_linkedin_x      │ 1 Hito / Logro       │ Copy celebratorio        │
│                      │ 1 Autor              │ Hashtags técnicos        │
├──────────────────────┼──────────────────────┼──────────────────────────┤
│ faq_tip_tecnico      │ 2+ Dudas comunes     │ FAQ: [Tema]              │
│                      │ Varios autores       │ Pregunta / Respuesta     │
├──────────────────────┼──────────────────────┼──────────────────────────┤
│ community_highlights │ 3+ Logros semanales  │ Narrativa unificada      │
│                      │ Múltiples autores    │ Cobertura del 100%       │
└──────────────────────┴──────────────────────┴──────────────────────────┘
```

1. **`post_linkedin_x` (Ruta `"logro"`)**:
    - **Objetivo:** Destacar hitos técnicos o certificaciones personales.
    - **Reglas:** Tono inspirador y profesional; mención explícita del autor y su logro exacto; prohibición absoluta de inventar certificaciones o instituciones no mencionadas; inclusión de 2 a 4 hashtags técnicos relevantes.
2. **`faq_tip_tecnico` (Ruta `"dudas"`)**:
    - **Objetivo:** Convertir patrones de preguntas recurrentes en activos educativos.
    - **Reglas:** Estructura fija en tres párrafos (`FAQ:`, `Pregunta:`, `Respuesta:`); consolidación de múltiples preguntas en una sola interrogante representativa; respuesta basada en buenas prácticas de ingeniería sin abarcar tecnologías no consultadas.
3. **`community_highlights` (Ruta `"periodo"`)**:
    - **Objetivo:** Celebrar el avance colectivo semanal o mensual de la comunidad.
    - **Reglas:** Tono inclusivo; cobertura estricta del 100% de los autores incluidos en las fuentes; redacción en prosa narrativa fluida evitando listas de viñetas (*bullet points*).
4. **Alerta Interna (Ruta `"bloqueo"`)**:
    - **Exclusión arquitectónica de IA:** Las alertas internas se generan mediante plantillas fijas en el grafo principal; no emplean LLMs ni requieren prompts.

## Uso

```python
from pipelines.communitylab import ejecutar_lote
from pipelines.communitylab.componentes_gemini import crear_componentes_gemini

salida = ejecutar_lote(lote, crear_componentes_gemini())  # requiere GEMINI_API_KEY y GEMINI_MODELOS
```

Para pruebas sin red: `crear_componentes_gemini(configuracion, transporte=GeminiFalso(...).transporte)`
(ver `pipelines/communitylab/gemini_falso.py`). Para simulación explícita: `simulados.crear_componentes`.

## Fidelidad editorial

Además de las reglas de los prompts (ajustadas: el alcance solo se describe si consta en la fuente;
la FAQ distingue recomendación de diagnóstico; los logros colectivos se presentan como del equipo),
`fidelidad.py` revisa cada texto frente a sus fuentes y el grafo guarda el resultado en
`advertencias_fidelidad` del activo (visible en curaduría y confirmado antes de aprobar):

| Tipo | Detecta |
|---|---|
| `cifra_no_sustentada` | Números ausentes de las fuentes, IDs y período. |
| `detalle_no_sustentado` | Posts/resúmenes que mencionan documentación, guías, configuración, despliegue, instalación, material, funciones o resultados que la fuente no menciona. |
| `archivo_no_sustentado` | Nombres de archivo ausentes de las fuentes. |
| `diagnostico_no_sustentado` | "la causa es", "carecía de", "se debe a"… sin respaldo en las fuentes. |
| `posible_atribucion_individual` | Fuente con logro colectivo y texto sin referencia al equipo. |

Limitaciones: son heurísticas léxicas en español. No detectan paráfrasis inventadas, nombres o
tecnologías nuevas, tono engañoso ni errores técnicos de una recomendación, y pueden dar falsos
positivos. No reemplazan la revisión humana ni el consentimiento antes de publicar. Los bloqueos
nunca llegan a un generador (router y defensa adicional en el grafo).

## Pruebas

- Sin red (CI): `python -m unittest discover -s pipelines/communitylab/tests`.
- Real y opcional: `COMMUNITYLAB_GEMINI_REAL=1 python tools/probar_gemini_real.py`
  (usa `ejemplos/peticiones_generadores.json`, datos ficticios).
