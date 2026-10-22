import type { AlmacenamientoOCI } from '@/services/api';
import { Cloud, CloudOff } from 'lucide-react';

// Copia de la versión aprobada en OCI Object Storage (backend/app/services/oci.py).
// Sin registro (activo nunca aprobado o API anterior) no muestra nada.
const ETIQUETA = { guardado: 'Guardado en OCI', error: 'Error al guardar en OCI', desactivado: 'OCI desactivado' } as const;
const CLASE = { guardado: 'badge-success', error: 'badge-danger', desactivado: 'badge-neutral' } as const;

function detalle(registro: AlmacenamientoOCI): string {
  const fecha = registro.fecha ? new Date(registro.fecha).toLocaleString('es') : 'fecha desconocida';
  if (registro.estado === 'guardado') return `Copia guardada el ${fecha} en ${registro.bucket ?? 'el bucket'}: ${(registro.objetos ?? []).join(', ')}`;
  if (registro.estado === 'error') return `No se pudo guardar el ${fecha} (${registro.error ?? 'error desconocido'}). Se puede reintentar desde el servidor.`;
  return 'El servidor no tiene activada la copia en OCI Object Storage.';
}

export default function EstadoOCI({ registro, conDetalle = false }: { registro?: AlmacenamientoOCI | null; conDetalle?: boolean }) {
  if (!registro || !(registro.estado in ETIQUETA)) return null;
  const Icono = registro.estado === 'guardado' ? Cloud : CloudOff;
  const texto = detalle(registro);
  return <span className={conDetalle ? 'flex flex-wrap items-center gap-2' : 'inline-flex'}>
    <span className={`${CLASE[registro.estado]} inline-flex items-center gap-1`} title={texto}>
      <Icono className="w-3 h-3" aria-hidden="true" />{ETIQUETA[registro.estado]}
    </span>
    {conDetalle && <span className="text-xs text-muted-foreground break-all" translate="no">{texto}</span>}
  </span>;
}
