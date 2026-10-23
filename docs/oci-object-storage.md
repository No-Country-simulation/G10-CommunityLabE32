# OCI Object Storage: paquetes generados y activos aprobados

En el bucket privado `communitylab-activos-marketing` se guardan dos cosas.

**1. El paquete de cada procesamiento** (todo lo que genera la IA, como pide el enunciado). Al terminar un
trabajo, el worker sube su paquete de distribución: resumen de la comunidad (sentimiento predominante,
temas y alertas), borradores por formato y el propio registro de almacenamiento.

```
activos/<período>/<procesamiento_id>/paquete-distribucion.json
```

El registro queda en `resultado.almacenamiento` del trabajo (`pendiente` mientras sube, luego `guardado`,
`error` o `desactivado`). La subida ocurre después de guardar el trabajo en PostgreSQL: un fallo de OCI
nunca hace fallar el procesamiento. `POST /api/v1/procesar` devuelve el mismo paquete en la respuesta.

**2. Cada versión aprobada.** Cada vez que un activo se aprueba en Curaduría (o se reaprueba con texto
nuevo), la API guarda una copia de esa versión:

```
aprobados/<id_activo>/v<versión>/activo.json   # texto, versiones LinkedIn/X, fuentes y advertencias
aprobados/<id_activo>/v<versión>/banner.svg    # solo si hay banner generado para esa versión
```

El resultado queda en `activos.almacenamiento_oci` (`guardado`, `error` o `desactivado`) y la API lo
devuelve en el campo del mismo nombre. Un fallo de OCI nunca impide aprobar.

## Acceso sin llaves (instance principal)

- Grupo dinámico `communitylab-vm-dg` (dominio Default): `instance.id = '<OCID de communitylab-vm>'`.
- Política `communitylab-vm-bucket-policy` (compartimento raíz): leer el namespace, leer ese bucket y
  crear, sobrescribir, listar y leer objetos en él. **No permite borrar.**
- No hay llaves de OCI en el `.env`, en la VM ni en el repositorio: el SDK (`oci==2.175.0`) obtiene un
  token temporal con la identidad de la instancia.

## Configuración

| Variable | Valor en la VM | Por defecto |
|---|---|---|
| `OCI_ALMACENAMIENTO` | `instance_principal` | `desactivado` (local y pruebas: no llama a OCI) |
| `OCI_BUCKET_NAME` | `communitylab-activos-marketing` | igual |
| `OCI_NAMESPACE` | opcional | se consulta una vez |

## Operación (contenedor de la API)

```bash
python -m backend.scripts.oci_almacenamiento --verificar                     # escribe y lee demo/verificacion-vm.txt
python -m backend.scripts.oci_almacenamiento --subir-aprobados               # cuenta aprobados sin copia
python -m backend.scripts.oci_almacenamiento --subir-aprobados --aplicar     # los sube y lo registra
```

Desactivar: `OCI_ALMACENAMIENTO=desactivado` y reiniciar la API. Los objetos ya subidos se conservan.
