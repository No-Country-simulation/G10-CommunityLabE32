import type { AlmacenamientoOCI } from '@/services/api';
import UiTree from '@/components/UiTree';
import { Cloud, CloudOff } from 'lucide-react';

// Copia de la versión aprobada en OCI Object Storage (backend/app/services/oci.py).
// Sin registro (activo nunca aprobado o API anterior) no muestra nada.
const ETIQUETA = { guardado: 'Guardado en OCI', error: 'Error al guardar en OCI', desactivado: 'OCI desactivado' } as const;
const CLASE = { guardado: 'badge-success', error: 'badge-danger', desactivado: 'badge-neutral' } as const;

// Texto corto para mostrar y versión completa (con las rutas de los objetos) para el título.
function detalle(registro: AlmacenamientoOCI): { corto: string; completo: string } {
  const fecha = registro.fecha ? new Date(registro.fecha).toLocaleString('es', { dateStyle: 'medium', timeStyle: 'short' }) : 'fecha desconocida';
  if (registro.estado === 'guardado') {
    const objetos = registro.objetos ?? [];
    const corto = `Guardada el ${fecha} · ${objetos.length} archivo(s)`;
    return { corto, completo: `${corto} en ${registro.bucket ?? 'el bucket'}: ${objetos.join(', ')}` };
  }
  if (registro.estado === 'error') {
    const corto = `Falló el ${fecha} (${registro.error ?? 'error desconocido'})`;
    return { corto, completo: `${corto}. Se puede reintentar desde el servidor.` };
  }
  const texto = 'El servidor no tiene activada la copia en OCI Object Storage.';
  return { corto: texto, completo: texto };
}

export default function EstadoOCI({ registro, conDetalle = false }: { registro?: AlmacenamientoOCI | null; conDetalle?: boolean }) {
  if (!registro || !(registro.estado in ETIQUETA)) return null;
  const Icono = registro.estado === 'guardado' ? Cloud : CloudOff;
  const { corto, completo } = detalle(registro);
  return <UiTree>{<span className={conDetalle ? 'flex flex-wrap items-center gap-2' : 'inline-flex'}>
    <span className={`${CLASE[registro.estado]} inline-flex items-center gap-1`} title={completo}>
      <Icono className="w-3 h-3" aria-hidden="true" />{ETIQUETA[registro.estado]}
    </span>
    {conDetalle && <span className="text-xs text-muted-foreground" title={completo}>{corto}</span>}
  </span>}</UiTree>;
}
