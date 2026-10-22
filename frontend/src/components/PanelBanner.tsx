'use client';


import UiTree from '@/components/UiTree';
import { useEffect, useRef, useState } from 'react';
import { ImageIcon, Loader2, CheckCircle2, XCircle, AlertTriangle, RefreshCw, Info, Download } from 'lucide-react';
import {
  describirError, generarBanner, listarBanners, revisarBanner, BannersActivo, ErrorLegible,
} from '@/services/api';

const ERROR_BANNER: Record<string, string> = {
  texto_insuficiente: 'El texto aprobado no tiene contenido suficiente para la tarjeta.',
  fallo_render: 'No se pudo generar la tarjeta. Puedes reintentar.',
};

// LinkedIn y X no aceptan SVG: el navegador dibuja el mismo banner en un canvas y lo baja en JPG.
// Se dibuja al doble de resolución para que el texto quede nítido al publicarlo.
async function descargarJpg(url: string, nombre: string) {
  const res = await fetch(url);
  if (!res.ok) throw new Error('No se pudo leer el banner.');
  const svg = URL.createObjectURL(new Blob([await res.text()], { type: 'image/svg+xml' }));
  try {
    const img = new Image();
    img.src = svg;
    await img.decode();
    const canvas = document.createElement('canvas');
    canvas.width = 2400;
    canvas.height = 1260;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('El navegador no permite dibujar el banner.');
    ctx.fillStyle = '#0b0b0b';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    const jpg = await new Promise<Blob | null>(ok => canvas.toBlob(ok, 'image/jpeg', 0.92));
    if (!jpg) throw new Error('No se pudo convertir el banner a JPG.');
    const enlace = document.createElement('a');
    enlace.href = URL.createObjectURL(jpg);
    enlace.download = nombre;
    enlace.click();
    setTimeout(() => URL.revokeObjectURL(enlace.href), 1000);
  } finally {
    URL.revokeObjectURL(svg);
  }
}

// Generar el banner es una acción separada de aprobar el texto, y aprobar el banner no lo publica.
export default function PanelBanner({ idActivo, estadoActivo, version }: {
  idActivo: string; estadoActivo: string; version: number;
}) {
  const [datos, setDatos] = useState<BannersActivo | null>(null);
  const [cargando, setCargando] = useState(true);
  const [accion, setAccion] = useState<'generar' | 'aprobado' | 'rechazado' | null>(null);
  const [error, setError] = useState<ErrorLegible | null>(null);
  const [refresco, setRefresco] = useState(0);
  const [descargando, setDescargando] = useState(false);
  const ocupadoRef = useRef(false);

  // Se recarga al cambiar de activo, de estado o de versión del texto.
  useEffect(() => {
    let vigente = true;
    listarBanners(idActivo)
      .then(res => { if (vigente) { setDatos(res); setCargando(false); } })
      .catch(e => { if (vigente) { setError(describirError(e)); setCargando(false); } });
    return () => { vigente = false; };
  }, [idActivo, estadoActivo, version, refresco]);

  const ejecutar = async (tipo: 'generar' | 'aprobado' | 'rechazado', fn: () => Promise<unknown>) => {
    if (ocupadoRef.current) return;
    ocupadoRef.current = true;
    setAccion(tipo);
    setError(null);
    try {
      await fn();
      setRefresco(n => n + 1);
    } catch (e) {
      setError(describirError(e));
    } finally {
      ocupadoRef.current = false;
      setAccion(null);
    }
  };

  const vigente = datos?.vigente ?? null;
  const anterior = datos?.banners.find(b => b.desactualizado && b.estado === 'generado') ?? null;
  const mostrado = vigente ?? anterior;

  const descargar = async () => {
    if (!mostrado?.url || descargando) return;
    setDescargando(true);
    setError(null);
    try {
      await descargarJpg(mostrado.url, `banner-${idActivo}-v${mostrado.version_texto}.jpg`);
    } catch (e) {
      setError({ tipo: 'desconocido', titulo: 'No se pudo descargar', mensaje: e instanceof Error ? e.message : 'Inténtalo de nuevo.', errores: [] });
    } finally {
      setDescargando(false);
    }
  };

  return <UiTree>{(
    <div className="card p-5">
      <div className="flex justify-between items-center mb-3 gap-2">
        <label className="text-xs font-semibold text-subtle-foreground uppercase tracking-wider flex items-center gap-2">
          <ImageIcon className="w-4 h-4" /> Banner
        </label>
        {vigente && (
          <span className={vigente.revision === 'aprobado' ? 'badge-success'
            : vigente.revision === 'rechazado' ? 'badge-danger'
            : vigente.estado === 'error' ? 'badge-danger' : 'badge-warning'}>
            {vigente.estado === 'error' ? 'Error'
              : vigente.estado !== 'generado' ? 'Generando'
              : vigente.revision === 'pendiente' ? 'Pendiente de revisión' : `Banner ${vigente.revision}`}
          </span>
        )}
      </div>

      {cargando ? (
        <Loader2 className="w-5 h-5 animate-spin text-primary" />
      ) : (
        <>
          {mostrado?.url && (
            <div className="relative">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`${mostrado.url}?v=${encodeURIComponent(mostrado.actualizado)}`}
                alt={`Vista previa del banner, versión ${mostrado.version_texto} del texto`}
                className={`w-full rounded-xl border border-border aspect-[1200/630] object-cover ${mostrado.desactualizado ? 'opacity-50' : ''}`}
              />
              {!mostrado.desactualizado && (
                <button type="button" onClick={descargar} disabled={descargando} className="banner-descarga"
                  aria-label="Descargar banner en JPG" title="Descargar en JPG">
                  {descargando ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" /> : <Download className="w-4 h-4" aria-hidden="true" />}
                  <span>JPG</span>
                </button>
              )}
              {mostrado.desactualizado && (
                <span className="badge-warning absolute top-2 left-2">
                  <AlertTriangle className="w-3 h-3" /> Desactualizado (texto v{mostrado.version_texto})
                </span>
              )}
            </div>
          )}
          {vigente?.estado === 'error' && (
            <p className="text-sm text-danger flex items-start gap-2">
              <XCircle className="w-4 h-4 mt-0.5 shrink-0" />
              {ERROR_BANNER[vigente.error_codigo ?? ''] ?? 'La generación falló.'}
            </p>
          )}
          {!datos?.puede_generar && (
            <p className="mt-3 text-xs text-muted-foreground flex items-start gap-2">
              <Info className="w-4 h-4 shrink-0" />
              {anterior ? 'El texto cambió o dejó de estar aprobado: aprueba el texto de nuevo para generar un banner actualizado.'
                : 'Aprueba el texto para generar el banner.'}
            </p>
          )}
          {error && (
            <p role="alert" className="mt-3 text-sm text-danger flex items-start gap-2">
              <XCircle className="w-4 h-4 mt-0.5 shrink-0" /> <span><strong>{error.titulo}.</strong> {error.mensaje}</span>
            </p>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            {datos?.puede_generar && (!vigente || vigente.estado === 'error') && (
              <button disabled={!!accion} onClick={() => ejecutar('generar', () => generarBanner(idActivo))} className="btn-primary">
                {accion === 'generar' ? <Loader2 className="w-4 h-4 animate-spin" />
                  : vigente?.estado === 'error' ? <RefreshCw className="w-4 h-4" /> : <ImageIcon className="w-4 h-4" />}
                {vigente?.estado === 'error' ? 'Reintentar banner' : 'Generar banner'}
              </button>
            )}
            {vigente?.estado === 'generado' && (
              <>
                <button disabled={!!accion || vigente.revision === 'rechazado'}
                  onClick={() => ejecutar('rechazado', () => revisarBanner(vigente.id, 'rechazado'))} className="btn-danger-soft">
                  <XCircle className="w-4 h-4" /> Rechazar banner
                </button>
                <button disabled={!!accion || vigente.revision === 'aprobado'}
                  onClick={() => ejecutar('aprobado', () => revisarBanner(vigente.id, 'aprobado'))} className="btn-success">
                  <CheckCircle2 className="w-4 h-4" /> Aprobar banner
                </button>
              </>
            )}
          </div>
          <p className="mt-3 text-xs text-subtle-foreground">
            Plantilla CommunityLab ({datos?.generacion_ia ? 'IA' : 'sin IA'}) con el texto aprobado. La aprobación del banner no lo publica.
          </p>
        </>
      )}
    </div>
  )}</UiTree>;
}
