# CommunityLab — Frontend actual

Copia local del frontend con los cambios de diseño actuales.

## Ejecutar

1. Instala Node.js 20.9 o superior.
2. Abre una terminal en esta carpeta.
3. Ejecuta `npm ci`.
4. Ejecuta `npm run dev -- --hostname 127.0.0.1 --port PUERTO_LIBRE` sustituyendo PUERTO_LIBRE por un puerto disponible.
5. Abre `http://localhost:PUERTO_LIBRE`.

Incluye el código, las ilustraciones, las fuentes, la configuración local y el archivo de bloqueo de dependencias. Se excluyen node_modules, .next, cachés y registros generados; se regeneran al instalar y ejecutar.

La configuración .env.local conserva la vista previa local y los datos de referencia. Las operaciones reales requieren el backend.
