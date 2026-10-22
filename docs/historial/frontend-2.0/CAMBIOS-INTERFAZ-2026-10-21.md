# Ajustes de interfaz · 21 de octubre de 2026

Trabajo aplicado únicamente en Frontend 2.0 2020-26 9-44. No se modificaron API, interceptor, sesión, backend ni repositorio remoto.

## Aplicado

- Interacciones responsive: lectura completa de mensajes en tarjetas en móvil; tabla desplazable en escritorio. Paginación y búsqueda permanecen en el servidor.
- Filtros adicionales de neutrales e indeterminados, estados vacíos claros y texto con la búsqueda aplicada.
- Campanita fuerza Pendientes incluso desde la propia Curaduría y vuelve al listado móvil.
- Denegados es una tabla de nombre, contenido/mensaje, motivo y fecha. Sin datos inventados y con estados de carga/error/vacío.
- Curaduría presenta un resumen legible de cada contenido, en lugar de priorizar IDs largos; lista navegable con teclado.
- LinkedIn y X abren las redes en una pestaña aparte, sin publicar ni adjuntar datos.
- Embudo de Analítica con etiquetas editoriales correctas; sentimientos con verde para positivo, azul para negativo, gris para neutral y amarillo para indeterminado.
- Requisitos de ingesta visibles en tarjeta junto a Procesar pendientes, con ancho y altura iguales en escritorio.
- Menú móvil con rutas disponibles, foco contenido en el diálogo y cierre con Escape.
- Advertencias de mayor contraste en tema claro, manteniendo la paleta.
- Resumen compacto con presentación desplegable. Alertas con diálogo Ver mensaje.
- Claridad editorial de cuenta, acceso y equipo; mostrar/ocultar contraseña y requisitos consistentes de diez caracteres. No se modificaron llamadas de autenticación.

## Dependencias que siguen fuera del frontend

El servidor debe aplicar q, entregar clasificación por tipo y motivos de denegación, resolver nombres de Discord y fechas, validar fidelidad, generar banners con la plantilla actualizada y guardar en OCI. Recuperación de contraseña, resolver/asignar alertas y el módulo real de Usuarios no se simularon con botones o endpoints inexistentes. La ruta Usuarios publicada no está incluida en los fuentes de esta copia; requiere integrar el módulo real del equipo.

Las pruebas visuales usan datos ficticios en un servidor aislado; no editan contenido publicado. Ver los detalles de verificación en el informe de revisión y PENDIENTES-BACKEND.md.

## Verificación final

- npx tsc --noEmit: correcto.
- npm run lint: correcto.
- npm run build: correcto.
- Revisión visual a 375 y 1920 px, claro y oscuro, con servidor de datos ficticios aislado.
- Verificados: menú móvil, filtro neutral, búsqueda sin resultados, campanita desde Aprobados, editor, tabla de denegaciones, enlaces a redes y diálogo de mensaje.
- api.ts y RutaProtegida.tsx coinciden byte a byte con el respaldo anterior a estos ajustes.
