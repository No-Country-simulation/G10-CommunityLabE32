# Frontend de CommunityLab

Panel web de CommunityLab: Next.js 16, React, TypeScript y Tailwind CSS. Descripción general,
arquitectura y despliegue en el `README.md` de la raíz.

## Pantallas (`src/app/`)

| Ruta | Pantalla |
|---|---|
| `/` | Resumen: totales y listados de mensajes, borradores, aprobados y alertas |
| `/ingesta` | Conectar Discord, subir lotes, procesar pendientes y Datos cargados (administradores) |
| `/interacciones` | Mensajes con autor, tipo, tema y sentimiento; búsqueda y filtros |
| `/curaduria` | Revisión, edición, banners, aprobación o denegación; estado de la copia en OCI |
| `/analitica` | Sentimiento, embudo de curaduría, temas y tipos de participación por lotes |
| `/usuarios` | Cuentas y roles (administradores) |
| `/configuracion`, `/equipo`, `/login`, `/register` | Cuenta, equipo e inicio de sesión |

## Conexión con la API

- Todas las llamadas pasan por `src/services/api.ts` con base `/api`. Next.js las reenvía a la API con el
  *rewrite* de `next.config.ts` (`API_PROXY_TARGET`, por defecto `http://127.0.0.1:8000`); en la VM lo hace nginx.
- **Sesión:** cookie HttpOnly `cl_sesion` que pone el servidor y token CSRF en memoria, enviado en
  `X-CSRF-Token` en cada escritura. No se guarda ningún token en `localStorage` (`docs/politica-acceso.md`).
- `RutaProtegida` pide la sesión al servidor antes de mostrar cada pantalla; los permisos los vuelve a
  comprobar la API en cada petición.

## Desarrollo

Con la API corriendo en `http://127.0.0.1:8000` (por ejemplo, con el Docker Compose de la raíz):

```bash
npm ci
npm run dev
```

Abrir http://localhost:3000. Si la API está en otra dirección:

```bash
API_PROXY_TARGET=http://127.0.0.1:8010 npm run dev
```

El *rewrite* se calcula al compilar: para `npm run build` + `npm start`, `API_PROXY_TARGET` debe
definirse antes del build.

## Verificación

```bash
npx tsc --noEmit
npm run lint
npm run build
```

En Docker, la imagen se construye con `frontend/Dockerfile` y la sirve el servicio `web` detrás del proxy.
