# Bot Discord: respuestas y alertas — aporte de Paulo

Implementación local del 08/10, preparada para PR el 09/10/2026 para la actividad compartida con Fabián, prevista
para el 09/10. Implementa conexión, recepción, ejecución de decisiones y transporte
de respuestas/alertas. La lógica de clasificación y generación corresponde a
Fabián y se incorpora como función asíncrona configurable.

El código está preparado para esa conexión, pero todavía no se ha usado un bot
real ni se ha recibido la implementación final de Fabián. La aceptación de la
división de trabajo no equivale a aceptación del contrato técnico aquí propuesto.

## Comportamiento

- Solo recibe mensajes nuevos de personas en los canales de texto configurados.
  Descarta otros servidores, DMs, bots, webhooks, mensajes del sistema, mensajes
  sin texto, hilos y foros. El canal interno nunca es canal de entrada.
- Guarda cada fuente en SQLite antes de procesarla. Clave única: servidor/mensaje.
  Repetir el evento no repite el envío; un ID con contenido distinto se rechaza.
- Invoca la función de Fabián con el evento `discord-source-v1`, el mismo contrato
  de entrada del lector preparado con Santiago. No modifica aquel lector.
- Una duda recibe la respuesta de Fabián como respuesta al mensaje original,
  sin activar menciones ni vistas previas de enlaces.
- Un bloqueo se dirige únicamente al canal interno. Si también es duda o logro,
  el bloqueo prevalece. Una decisión con bloqueo y respuesta pública se rechaza.
- Un testimonio queda identificado en el registro local; no se publica ni se
  convierte automáticamente en un post. Consentimiento y curaduría siguen aparte.
- Una decisión no puede elegir canal, servidor ni autor. Los destinos se derivan
  de la fuente validada y de la configuración local, nunca de texto generado.
- Verifica permisos al iniciar, al reanudar y antes de enviar. Comprueba que el
  canal interno no sea visible para @everyone ni para roles/usuarios ajenos a la
  lista configurada. También revisa permisos individuales de usuarios fuera de caché.
  Los administradores y propietario conservan su acceso inherente de Discord.

## Archivos

- `bot_discord/`: contratos, cliente discord.py, orquestación, cola y CLI.
- `CONTRATO_PARA_FABIAN.md`: entrada, salida, responsabilidades y ejemplos.
- `config.example.json`: IDs ficticios; no es una configuración utilizable en vivo.
- `tests/`: pruebas de transporte, privacidad, fallos y compatibilidad.
- `tools/validate_local.py`: comprobación reproducible con red externa bloqueada.
- `VALIDACION.md`: alcance de las pruebas. `evidencias/` se genera localmente y no se versiona.
- El validador utiliza el repositorio que contiene esta carpeta; no necesita una copia externa.

## Usar lo preparado localmente

En PowerShell, desde esta carpeta:

```powershell
.\.venv\Scripts\python.exe -B -m bot_discord --config config.example.json check-config
.\.venv\Scripts\python.exe -B tools\validate_local.py
```

El primer comando valida el archivo sin conectar; el segundo ejecuta pruebas con
datos y transporte simulados. No necesitan token. La carpeta `.venv` debe crearse siguiendo los comandos de instalación; no se versiona. `requirements.txt` fija la dependencia
de ejecución; `requirements-validacion.lock.txt` conserva el entorno completo.

Para recrear el entorno con Python 3.12:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-validacion.lock.txt
```

## Conexión real pendiente

Estos pasos son instrucciones para la validación futura; no se ejecutaron:

1. Acordar el contrato con Fabián y disponer de su módulo Python. Si su lógica
   vive detrás de una API, acordar el endpoint/autenticación y escribir un adaptador
   al mismo contrato; no hay un endpoint de bot verificado en el repositorio actual.
2. Crear/invitar un bot oficial al servidor de pruebas y activar Message Content
   Intent. Configurar View Channel, Send Messages y Read Message History en los
   canales autorizados. El bot no requiere Administrator, Members ni Presence Intent.
3. Copiar `config.example.json` a `config.json`; reemplazar servidor, canales,
   canal interno y roles internos por IDs reales. El canal interno debe ser
   privado para el equipo. `internal_user_ids` permite excepciones individuales
   explícitas. Los IDs no son claves; el token no se guarda en ese archivo.
4. Proporcionar `DISCORD_BOT_TOKEN` al proceso por un mecanismo local seguro.
   Este programa no busca ni abre archivos `.env` y no imprime el token.
5. Cuando se autorice la prueba real, ejecutar:

```powershell
.\.venv\Scripts\python.exe -B -m bot_discord --config config.json listen --connect --processor fabian_adapter:procesar
```

`fabian_adapter:procesar` es el nombre propuesto para el módulo de Fabián; no se
incluye una lógica simulada que pueda activarse por defecto en un servidor real.
Su función debe ser `async def`, respetar cancelación y devolver el contrato.

## Operación y recuperación

La CLI impide dos instancias simultáneas sobre la misma base. La cola tiene un
límite configurable de registros; al llenarse detiene el cliente en lugar de borrar
registros usados para deduplicación. Un solo consumidor procesa los mensajes
secuencialmente. SQLite se usa en disco local, no en una carpeta de red.

Con el bot detenido:

```powershell
.\.venv\Scripts\python.exe -B -m bot_discord --config config.json status
.\.venv\Scripts\python.exe -B -m bot_discord --config config.json retry --key 100:600
```

El segundo comando es un ejemplo con IDs ficticios. Solo reencola un fallo de
procesador (`failed_processing`) o de verificación previa al envío
(`blocked_delivery`). No conecta ni envía por sí mismo. Reintentar después de
corregir la causa; el siguiente arranque procesa la cola.

Los estados `queued` y `ready` sobreviven a reinicios. Al arrancar, y bajo bloqueo
de instancia, `processing` se reencola y `checking` vuelve a `ready`: todavía no
había comenzado el envío. `sending` pasa a `uncertain`, pues Discord pudo recibirlo.
Una excepción durante el envío también deja `uncertain`. Esos casos requieren
revisar el mensaje real y no tienen reintento automático ni comando de reenvío.
`sent` conserva el ID devuelto por Discord; `recorded` identifica un resultado
sin publicación, como un testimonio.

Esta estrategia evita repetir automáticamente un envío dudoso a nivel de la
aplicación; no promete entrega exactamente una vez. discord.py gestiona sus
propios límites de frecuencia y reintentos HTTP. No borrar la base para solucionar
errores: se perdería la memoria de duplicados. Los registros contienen mensajes
y resultados: conservarlos localmente, fuera del repositorio y de las evidencias
compartidas, y acordar su retención antes de operar con datos reales.

## Relación con el repositorio y límites

La referencia de partida es main `61ddc4bd4a6dfa0590b44e9d833e2fd42769f563`.
Este PR se apoya en el PR #20 del lector. Las pruebas de compatibilidad usan
`../reader`; después de integrar el lector se podrá cambiar la base a main.
El validador registra HEAD y compara las fuentes versionadas antes y después.

Las pruebas importan los esquemas `Interaccion`/`IngestaRequest`, ejecutan los nodos
de análisis y FAQ con la llamada LLM sustituida, y ejercitan las cuatro rutas del
grafo. Un borrador generado por el grafo no se considera automáticamente una
respuesta autorizada del bot. La normalización completa de mensajes al pipeline
pertenece a Santiago; aquí solo hay conversiones ficticias dentro de pruebas.

El lector de `../reader` puede seguir sirviendo al pipeline. Este bot no consume su
SQLite: tiene su propia conexión/cola y comparte el formato fuente. No iniciar
dos instancias de este bot con bases distintas sobre los mismos canales, porque
la deduplicación es local a cada base.

Pendientes de validación conjunta: módulo de Fabián, configuración/permisos reales,
respuesta visible en Discord, alerta exclusivamente interna, consumo acordado con
el resto del sistema y despliegue. No se probaron IA real, VM ni PostgreSQL.
No hay lectura retrospectiva, recuperación de mensajes perdidos durante desconexión,
procesamiento de ediciones/borrados, OAuth ni botón de conexión.

Referencia de la API utilizada: [discord.py — envío de mensajes](https://discordpy.readthedocs.io/en/latest/api.html#discord.abc.Messageable.send).
