# Política de acceso y sesiones

Código: `backend/app/core/acceso.py` (dependencias), `backend/app/services/auth.py` (sesiones),
`backend/app/services/limite_login.py` (intentos), `backend/app/routers/auth.py` (cuentas).
Pruebas: `worker/tests/test_acceso_seguridad.py`.

## Credenciales

Las tres credenciales **no son intercambiables**.

| Credencial | Quién | Cómo viaja | Vale para |
|---|---|---|---|
| Sesión de persona | Navegador | Cookie `cl_sesion` (HttpOnly, Secure, SameSite=Strict, Path=/api) + cabecera `X-CSRF-Token` en POST/PATCH | Según el rol de la cuenta |
| Token de operador (`OPERADOR_TOKEN`) | Scripts y terminal | Cabecera `X-Operador-Token` | Rutas de rol operador. **Nunca** administración ni puente. No se usa en el navegador. |
| Token del puente (`PUENTE_TOKEN`) | Servicio `discord-bridge` | `Authorization: Bearer …` | `/api/v1/puente/*` y entrega/consulta de lotes en `/api/v1/trabajos` |

### Roles

El rol se guarda en `usuarios.rol` y se lee de la base **en cada petición**. Nunca viene del token ni
de datos enviados por el cliente.

- **usuario**: lee agregados sin textos.
- **operador**: lo anterior, más los datos comunitarios y las acciones.
- **administrador**: lo anterior, más la gestión de cuentas.

## Sesión

- **Token.** JWT HS256 firmado con `JWT_SECRET_KEY`.
  - Se exigen `exp`, `iat`, `sub` (id numérico), `jti` y `typ=sesion`, y solo se acepta el algoritmo HS256.
  - El `jti` identifica una fila de `sesiones`: el token solo vale si esa fila existe, no está revocada ni
    vencida, y el usuario está habilitado.
- **Revocación inmediata.** Se produce en estos casos:
  - logout;
  - un administrador cambia el rol o deshabilita la cuenta (se revocan todas sus sesiones);
  - la persona cambia su contraseña (se revocan sus otras sesiones).
- **Expiración.** `SESION_HORAS`, 8 h por defecto (de 1 a 72). No hay renovación automática: al vencer, se
  vuelve a iniciar sesión.
- **CSRF.** El token CSRF es un HMAC de la sesión: no se almacena y se recupera con `GET /api/auth/sesion`
  tras recargar. El navegador lo guarda solo en memoria. Se exige en toda petición con cookie que modifique estado.
- **Clave no válida.** Si `JWT_SECRET_KEY` falta, mide menos de 32 bytes o es una de las claves que
  estuvieron publicadas en el repositorio, el login y las rutas con sesión responden **503**
  `autenticacion_no_configurada`. Los healthchecks, el puente y el token de operador siguen funcionando.

**Límites conocidos.**
- Las sesiones dependen de PostgreSQL (una consulta por petición autenticada).
- Revocar exige que la base esté disponible.
- No hay «cerrar todas las sesiones» para la propia persona, salvo cambiar la contraseña.

## Registro y primer administrador

- **Registro público.** `REGISTRO_PUBLICO=false` por defecto, en cuyo caso `POST /api/auth/register` responde
  403 `registro_deshabilitado`. Si se habilita, crea siempre cuentas de rol `usuario`, y enviar `rol` da 422.
- **Primer administrador.** Sin credenciales predeterminadas. La contraseña se escribe sin eco o se lee de la
  entrada estándar, y nunca va como argumento:
  ```
  docker compose exec api python -m backend.scripts.crear_usuario --email <correo> --rol administrador
  ```
  Después, el administrador crea cuentas con `POST /api/auth/usuarios` y las gestiona con
  `PATCH /api/auth/usuarios/{id}` (rol, habilitación y contraseña temporal), también desde la pantalla
  **Usuarios** del panel (solo administradores).
  - **Verificación.** Antes de dar por terminado un despliegue, ejecutar
    `python -m backend.scripts.verificar_acceso --email <correo>`. Hace login, consulta la sesión y una
    lectura del rol, e imprime solo los códigos.
  - **Recuperación.** Si se pierde la contraseña del administrador o queda deshabilitado, ejecutar
    `crear_usuario ... --restablecer`. Cambia contraseña, rol y habilitación de una cuenta existente y revoca
    sus sesiones.
  - **Procedimiento completo en la VM:** `docs/operacion-vm.md`, sección «Primer administrador».
- **Contraseñas.** De 10 caracteres a 72 bytes (límite de bcrypt).

## Intentos de login

- **Límite.** Ventana deslizante en memoria del proceso de la API:
  - `LOGIN_MAX_INTENTOS` fallos por IP y correo (5);
  - `LOGIN_MAX_INTENTOS_IP` por IP (30);
  - en `LOGIN_VENTANA_SEGUNDOS` (900).

  Al superarlo, la respuesta es 429. El bloqueo es temporal y nunca se cuenta por correo solo, para que un
  tercero no pueda bloquear una cuenta ajena desde otra IP.
- **IP real.** nginx sobrescribe `X-Real-IP` con `$remote_addr`. La API solo acepta esa cabecera si la
  conexión llega desde un proxy declarado en `LOGIN_PROXY_CONFIABLE`: nombres DNS o IP/CIDR. En Compose es
  `proxy`, resuelto con caché de 30 s. Sin esa variable, o desde otro origen (`web`, el puente o un cliente
  directo), se usa la IP real de la conexión, así que falsificar la cabecera no reinicia el contador.
  La API no publica puertos en producción.
- **Topología.** Un único proceso uvicorn. Con varias réplicas, el contador debería compartirse.
- **Respuesta uniforme.** La misma (401 `credenciales_invalidas`) si la cuenta no existe, está
  deshabilitada o la contraseña no coincide. No se registran contraseñas ni tokens.

## Política por endpoint

| Endpoint | Anónimo | usuario | operador | admin | Puente | Token operador |
|---|---|---|---|---|---|---|
| `GET /`, `GET /health`, `/healthz` (nginx) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| `POST /api/auth/login` | ✔ (límite) | — | — | — | — | — |
| `POST /api/auth/register` | solo con `REGISTRO_PUBLICO=true` | — | — | — | — | — |
| `GET /api/auth/sesion`, `POST /api/auth/logout`, `GET/PATCH /api/auth/me` | ✖ | ✔ | ✔ | ✔ | ✖ | ✖ |
| `GET/POST/PATCH /api/auth/usuarios…` | ✖ | ✖ | ✖ | ✔ | ✖ | ✖ |
| `GET /api/dashboard/kpis`, `/ambitos`, `GET /api/mensajes/sentimiento/resumen` (agregados) | ✖ | ✔ | ✔ | ✔ | ✖ | ✔ |
| `GET /api/mensajes` (textos y autores) | ✖ | ✖ | ✔ | ✔ | ✖ | ✔ |
| `GET/PATCH /api/curaduria/activos…` (borradores, toda edición) y `POST …/posts/generar` (IA, máx. 3 por borrador) | ✖ | ✖ | ✔ | ✔ | ✖ | ✔ |
| Banners: listar, generar, revisar y `GET /api/banners/{id}.svg` | ✖ | ✖ | ✔ | ✔ | ✖ | ✔ |
| `POST /api/mensajes/procesamientos` (subir archivo) | ✖ | ✖ | ✔ | ✔ | ✖ | ✔ |
| `POST/GET /api/v1/procesamiento-pendientes…` | ✖ | ✖ | ✔ | ✔ | ✖ | ✔ |
| `POST/GET /api/v1/trabajos…` (lotes) | ✖ | ✖ | ✔ | ✔ | ✔ | ✔ |
| `POST /api/v1/puente/solicitudes/…` | ✖ | ✖ | ✖ | ✖ | ✔ | ✖ |
| `/api/v1/discord/historico/*` | ✖ | ✖ | ✔ (solo las suyas) | ✔ (todas) | ✖ | ✔ (las del token) |
| `POST /api/v1/procesamientos`, `/upload` (mock obsoleto) | ✖ | ✖ | ✔ | ✔ | ✖ | ✔ |

**Respuestas de error.**
- **Sin credencial:** 401.
- **Rol insuficiente:** 403 `permiso_insuficiente`.
- **Sin CSRF:** 403 `csrf_invalido`.
- **Credencial no configurada en el servidor:** 503.
  - `OPERADOR_TOKEN` o `PUENTE_TOKEN`: `acceso_no_configurado`.
  - `JWT_SECRET_KEY`: `autenticacion_no_configurada`.

**Rutas obsoletas.** `POST /api/v1/procesamientos` y `/upload` no encolan, no guardan y no llaman a la IA.
No tienen consumidores en la interfaz; solo `infrastructure/docker/validacion/probar_integracion.py`.
Siguen protegidas mientras dure la transición; retirarlas exige actualizar ese script.

**Importaciones históricas.** Pertenecen a quien las solicitó (`usuario:<id>` o `operador:token-compartido`).
- Una importación ajena responde 404, igual que una inexistente.
- La `Idempotency-Key` de una persona se acota a su cuenta.
