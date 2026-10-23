# Guía de Contribución — CommunityLab

## 1. Ramas

El proyecto utiliza una rama principal para mantener la versión estable.

Las ramas de trabajo se crean para desarrollar tareas específicas.

Convención:

- `feat/<nombre-tarea>` (o `feature/<nombre-tarea>`) — nueva funcionalidad
- `fix/<nombre-error>` — corrección de errores
- `chore/<nombre-tarea>` — configuración o mantenimiento
- `docs/<nombre-tarea>` — documentación

No se deben realizar cambios directamente sobre la rama principal: `main` está protegida y no admite *push* directo,
*force push* ni borrado.

## 2. Convención de commits

Los commits deben utilizar una estructura clara:

`tipo: descripción breve`

Tipos permitidos:

- `feat` — nueva funcionalidad
- `fix` — corrección de errores
- `docs` — documentación
- `test` — pruebas
- `refactor` — reorganización del código
- `chore` — configuración o mantenimiento

Ejemplo:

`feat: agregar endpoint de procesamientos`

El título del Pull Request sigue la misma convención (tipo en minúsculas y descripción que empieza en
minúscula). Lo valida el check «Validar Título del PR».

## 3. Pull Request

Los cambios deben enviarse mediante un Pull Request antes de incorporarse a la rama principal.

Cada Pull Request debe explicar:

- Qué cambio se realizó.
- Qué tarea del cronograma corresponde.
- Qué pruebas se realizaron.
- Si fue necesario actualizar documentación.

El repositorio contiene una plantilla de Pull Request en:

`.github/PULL_REQUEST_TEMPLATE.md`

## 4. Revisión

Antes de incorporar un cambio a la rama principal, el Pull Request debe ser revisado por otro integrante del equipo.

La regla de `main` exige:

- Al menos **una aprobación** de otro integrante.
- Todas las conversaciones de revisión resueltas.
- El check «Validar Título del PR» en verde, con la rama **al día** con `main`.

## 5. Merge

El merge se realizará después de la revisión y aprobación correspondiente. Si `main` avanzó, primero se actualiza
la rama del Pull Request y se espera a que los checks vuelvan a pasar.

## 6. Seguridad

No se deben subir credenciales, claves API, contraseñas ni archivos `.env` al repositorio.

El archivo `.gitignore` debe mantenerse actualizado para evitar publicar información sensible.

## 7. Relación con el cronograma

Los cambios realizados deben relacionarse, cuando corresponda, con la tarea correspondiente del cronograma de CommunityLab.