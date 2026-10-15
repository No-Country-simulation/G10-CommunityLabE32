# Integrar Discord en vivo — aporte de Paulo

Trabajo local iniciado el 7 de octubre de 2026 para CommunityLab, equipo 32.
Esta entrega implementa la recepción de mensajes nuevos de canales de texto
autorizados y su almacenamiento local para el posterior trabajo de Santiago.
La implementación local pasó 19 pruebas automatizadas con datos ficticios.
La conexión a un servidor real de Discord sigue pendiente. Ver VALIDACION.md.

## División confirmada del trabajo

- **Paulo:** conexión, lista de servidor y canales autorizados, captura de mensajes,
  exclusión de bots/webhooks/sistema, almacenamiento local y entrega del evento fuente.
- **Santiago (Tian):** normalización al esquema común, validación del contenido,
  agrupación en lotes y adaptación al punto de entrada acordado con el backend.
- **Ambos:** acordar el contrato y validar el recorrido completo. Esta distribución
  fue confirmada por Santiago en el mensaje compartido por Paulo el 07/10/2026.
  El formato técnico de intercambio todavía debe acordarse.

El lector no responde mensajes, publica, clasifica con IA ni encola trabajos.
El bot que responderá dudas corresponde a la actividad posterior con Fabián.
La base SQLite de esta carpeta es únicamente una bandeja local del lector;
no sustituye PostgreSQL ni modifica la arquitectura del repositorio del equipo.

## Archivos

- `discord_reader/core.py`: configuración y filtrado del evento.
- `discord_reader/__main__.py`: cliente Discord y comandos de uso.
- `discord_reader/store.py`: bandeja SQLite con deduplicación persistente y exportación JSONL.
- `config.example.json`: IDs ficticios y capacidad máxima de la bandeja.
- `examples/mensaje_ficticio.json`: propuesta de evento fuente para Tian.
- `tests/test_reader.py` y `tests/test_client.py`: 19 pruebas locales aprobadas.
- `requirements.lock.txt`: versiones exactas instaladas en la validación local.
- `CONTRATO_PARA_TIAN.md`: campos entregados y decisiones de integración pendientes.

## Comportamiento y alcance

La configuración exige un servidor y una lista no vacía de IDs de canales.
No permite comodines. Antes de acceder al texto, el filtro rechaza mensajes de
otros servidores o canales, mensajes privados, autores bot, webhooks y mensajes
del sistema. No almacena mensajes sin texto ni descarga adjuntos.

Esta primera versión admite canales de texto normales. No admite hilos ni foros,
ni hereda autorización de canales padre. Al conectarse comprueba los canales
configurados y el permiso de lectura; un fallo de configuración detiene el cliente.
La captura empieza después de verificar todos los canales. Los eventos que llegan
antes de esa verificación se descartan y se cuentan; no se recuperan automáticamente.
Al reanudar la sesión se vuelven a comprobar los canales, y cada evento autorizado
comprueba el permiso de lectura disponible en la caché del cliente. No se enumeran historiales ni se consulta contenido anterior.

Los mensajes se guardan sin cambiar su texto. Sus IDs se conservan como cadenas
para evitar pérdida de precisión. Se evita duplicar `(guild_id, message_id)` incluso
después de reiniciar. Las ediciones y eliminaciones posteriores no se sincronizan.

El cliente solicita reconexión de Discord mediante discord.py. Esto no garantiza
recuperar mensajes emitidos durante una caída, un reinicio o un cierre por error.
Al llenarse la bandeja o fallar una escritura, detiene la captura y reporta un código
de error; el mensaje que provocó el fallo y eventos pendientes pueden no guardarse.
La bandeja no se vacía al exportar. Su retención y consumo se acordarán con Tian.

La consola muestra estados, contadores y categorías de error, sin texto, nombres
ni token. La base y sus exportaciones sí contienen mensajes e identificadores:
se mantienen locales y están excluidos de Git. El permiso de lectura de un canal
no equivale a consentimiento para publicar su contenido.

## Preparación pendiente

1. Acordar con el equipo el servidor y los canales autorizados. Copiar sus IDs con
   el modo desarrollador de Discord; no usar nombres como identificadores.
2. Crear o usar una aplicación bot del equipo y concederle acceso únicamente a
   los canales aprobados. No necesita Administrador ni Enviar mensajes.
3. Habilitar **Message Content Intent** en el portal de desarrolladores. El código
   también lo solicita, junto con eventos de servidores y mensajes de servidor.
4. Copiar `config.example.json` a `config.json` y reemplazar los IDs ficticios.
   La ruta de la base se resuelve respecto de ese archivo de configuración.
5. Proporcionar el token mediante la variable de entorno `DISCORD_BOT_TOKEN`
   únicamente al ejecutar. No incluirlo en archivos compartidos, comandos guardados
   ni conversaciones. El programa no abre ni busca archivos `.env`.

## Comandos para una ejecución posterior

El entorno `.venv` no se incluye. Los comandos de instalación
permiten prepararlo en cada equipo; el comando de conexión real no se ha ejecutado.
Requieren Python 3.11 o superior y ejecutarse desde esta carpeta. La dependencia
principal validada es `discord.py==2.7.1`; las dependencias completas están en
`requirements.lock.txt` (entorno validado: Windows, Python 3.12.14).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m discord_reader --config config.json check-config
```

Después de establecer el token en el entorno y autorizar la conexión:

```powershell
.\.venv\Scripts\python.exe -m discord_reader --config config.json listen --connect
```

Detener con Ctrl+C. Para exportar los eventos a un archivo local nuevo:

```powershell
.\.venv\Scripts\python.exe -m discord_reader --config config.json export --output exports/mensajes-01.jsonl
```

La exportación no sobrescribe archivos existentes ni envía datos a ningún servicio.
Si la exportación falla a mitad, el archivo puede quedar incompleto: no entregarlo
a Tian como exportación terminada; usar un nombre nuevo al repetir.

Para repetir las pruebas sin conectar a Discord:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Estado y validación pendiente

Se ejecutaron las pruebas del núcleo y del adaptador con discord.py instalado,
pero sustituyendo las solicitudes y la conexión por simulaciones. También se validó
la configuración ficticia y la consistencia de las dependencias. No se abrió una
conexión real, ni se utilizaron credenciales reales.

Pendiente externo: disponer del bot, el servidor y los canales autorizados; habilitar
los permisos e intents necesarios; comprobar recepción y reconexión reales; acordar
el contrato con Santiago e integrar el normalizador. Esta entrega cubre la preparación
local de Paulo, no acredita todavía el cierre de la actividad compartida.

No se añadió la pantalla ni el flujo OAuth de conexión de usuarios: esa idea quedó
fuera de este alcance. La capacidad de la bandeja es configurable y la política de
consumo/retención se acordará al integrar ambas partes.

## Referencias consultadas

- [Inicio de discord.py](https://discordpy.readthedocs.io/en/stable/quickstart.html)
- [Intents y acceso al contenido](https://discordpy.readthedocs.io/en/stable/intents.html)
- [Gateway de Discord](https://docs.discord.com/developers/events/gateway#message-content-intent)

Referencia del contrato del proyecto: `backend/app/schemas/procesamientos.py`
en main `61ddc4bd4a6dfa0590b44e9d833e2fd42769f563`, revisado el 09/10/2026.
El lector es una entrada para el normalizador de Santiago. El bot de respuestas
es otra actividad y comparte el formato fuente, pero tiene su propio consumidor.
