# Configuración y verificación de Gemini API

Aporte a la actividad «Configurar la Gemini API (claves, cuotas y modelo de respaldo) y probar la conexión desde la VM», con entrega prevista el 24/09/2026. Responsable: Paulo.

Esta carpeta entrega una prueba reproducible de conexión con Python 3.10 o superior, sin instalar dependencias. Es independiente del backend, del worker y de Docker Compose: no activa procesamiento con IA en el proyecto.

## Archivos

- `probar_gemini.py`: envía una solicitud de texto sintético por modelo seleccionado a la API oficial de Google.
- `.env.example`: plantilla pública sin credenciales, con los modelos configurados en la verificación local del 24/09.
- `test_probar_gemini.py`: pruebas automatizadas sin conexión a Google y con claves ficticias.
- `.gitignore`: excluye credenciales privadas e informes generados.

## Configuración privada

Desde la raíz del repositorio, copiar la plantilla:

PowerShell:

```powershell
Copy-Item infrastructure/gemini/.env.example infrastructure/gemini/.env
```

Linux o macOS:

```sh
cp infrastructure/gemini/.env.example infrastructure/gemini/.env
chmod 600 infrastructure/gemini/.env
```

Editar ese `.env` local para reemplazar `coloca_tu_clave_privada`. También se pueden configurar `GEMINI_API_KEY`, `GEMINI_MODEL` y `GEMINI_FALLBACK_MODEL` mediante variables de entorno; estas tienen prioridad. No poner la clave en argumentos de consola, capturas, mensajes, código ni commits. La clave del responsable no se distribuye con esta entrega.

La plantilla refleja modelos verificados el 24/09/2026; confirmar su disponibilidad y las cuotas actuales para el proyecto en AI Studio antes de ejecutar. Este script no consulta ni modifica la facturación. El costo depende del modelo y del nivel del proyecto; una prueba correcta no acredita gratuidad. Para mantener el requisito de no pagar, usar únicamente un proyecto y modelos cuyo nivel gratuito se haya confirmado, sin habilitar facturación para esta prueba.

## Ejecutar la prueba real

Desde la raíz del repositorio:

```sh
python infrastructure/gemini/probar_gemini.py
python infrastructure/gemini/probar_gemini.py --rol principal
python infrastructure/gemini/probar_gemini.py --rol respaldo
```

Por defecto comprueba ambos roles. Cada comando hace una solicitud por rol seleccionado, con un máximo de salida de 256 tokens y 60 segundos de espera por solicitud. No hay reintentos ni conmutación automática; revisar errores 429 o 503 antes de repetir para evitar consumo innecesario. El respaldo no garantiza eludir restricciones compartidas del proyecto.

Si se usa otro archivo privado:

```sh
python infrastructure/gemini/probar_gemini.py --env-file /ruta/privada/gemini.env
```

El código de salida es `0` si todos los modelos seleccionados responden `OK_GEMINI`, `1` ante una prueba fallida o imposibilidad de guardar el informe y `2` ante configuración inválida. Los informes se guardan en `infrastructure/gemini/resultados/resultado-<rol>.json`, fuera de Git. No se guardan la clave, los cuerpos de error, razonamientos ni respuestas arbitrarias del servidor. La credencial viaja en la cabecera `x-goog-api-key`, mediante HTTPS, nunca en la URL.

## Evidencia y alcance del cierre

Las pruebas reales locales conservadas por Paulo, realizadas el 24/09/2026 con texto sintético, verificaron HTTP 200 y `OK_GEMINI` para `gemini-3.5-flash` y `gemini-3.1-flash-lite`. El principal presentó primero un 503 y respondió correctamente tras un reintento manual. Son evidencia histórica local, no resultados de una nueva llamada ni una garantía de disponibilidad.

En AI Studio se registraron ese día el nivel gratuito y estas cuotas del proyecto:

| Rol | Solicitudes/minuto | Tokens de entrada/minuto | Solicitudes/día |
| --- | ---: | ---: | ---: |
| Principal | 5 | 250.000 | 20 |
| Respaldo | 15 | 250.000 | 500 |

Estas cuotas son una observación del 24/09, no el saldo actual ni límites universales. Consultar el panel del proyecto antes de planificar lotes o demos. No se publica la credencial, el identificador privado del proyecto ni los archivos locales de evidencia.

Para cerrar toda la actividad queda repetir la conexión desde la VM del equipo cuando esté disponible y registrar fecha, modelos, resultado y referencia al informe sin secretos en la bitácora. La integración del pipeline, la calidad del análisis, las pruebas de carga y la conmutación automática corresponden a etapas posteriores.

## Verificar el script sin consumir la API

```sh
python -m unittest discover -s infrastructure/gemini -p "test_*.py" -v
```

Las pruebas cubren autenticación en cabecera, uso exclusivo de texto sintético, selección de roles, prioridad del entorno, configuración inválida, respuestas inesperadas, timeout y errores HTTP 401/429/503. Verifican que los informes y errores no expongan la clave ficticia. No requieren clave real ni VM.

Referencias: [generación de contenido](https://ai.google.dev/api/generate-content), [cuotas de Gemini API](https://ai.google.dev/gemini-api/docs/rate-limits), [facturación y niveles](https://ai.google.dev/gemini-api/docs/billing) y [panel de cuotas de AI Studio](https://aistudio.google.com/rate-limit).
