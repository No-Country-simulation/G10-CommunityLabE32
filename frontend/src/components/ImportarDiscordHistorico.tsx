'use client';

import { useEffect, useState } from 'react';
import {
  verificarCanalDiscord,
  previsualizarDiscordHistorico,
  crearImportacionDiscord,
  consultarImportacionDiscord,
  listarImportacionesDiscord,
  cancelarImportacionDiscord,
  reanudarImportacionDiscord,
  obtenerMensajesImportacionDiscord,
  describirError,
  VerificacionCanalDiscord,
  PrevisualizacionDiscord,
  ImportacionDiscord,
  MensajeHistoricoDiscord,
} from '@/services/api';
import {
  CheckCircle2,
  Eye,
  Download,
  XCircle,
  RotateCcw,
  Loader2,
  AlertTriangle,
  MessageSquare,
  Calendar,
  Hash,
} from 'lucide-react';

// La importación solo trae mensajes a tablas protegidas; el análisis con IA es otro paso.
const ETIQUETA_IA: Record<string, string> = {
  sin_evidencia: 'Importado · sin analizar',
  pendiente: 'Importado · análisis pendiente',
  fallido: 'Importado · análisis fallido',
  procesado: 'Analizado',
};
const ACTIVA = ['pendiente', 'ejecutando'];

const nuevaClave = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

export default function ImportarDiscordHistorico() {
  const [abierto, setAbierto] = useState(false);
  const [canalId, setCanalId] = useState('');
  const [desde, setDesde] = useState('2026-09-01');
  const [hasta, setHasta] = useState('2026-09-15');
  const [zona, setZona] = useState('America/Guatemala');
  const [incluirMuestra, setIncluirMuestra] = useState(true);
  const [confirmarAlcance, setConfirmarAlcance] = useState(false);

  const [cargandoAccion, setCargandoAccion] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [verificacion, setVerificacion] = useState<VerificacionCanalDiscord | null>(null);
  const [preview, setPreview] = useState<PrevisualizacionDiscord | null>(null);
  const [importacion, setImportacion] = useState<ImportacionDiscord | null>(null);
  const [mensajes, setMensajes] = useState<MensajeHistoricoDiscord[]>([]);
  const [totalMensajes, setTotalMensajes] = useState<number>(0);
  // Una clave por previsualización confirmada: reintentar el MISMO envío no duplica, y una
  // importación nueva del mismo rango (días después) no reutiliza la anterior.
  const [claveIntento, setClaveIntento] = useState<string>('');

  // Al recargar: recuperar la importación activa (o la más reciente) de esta cuenta.
  useEffect(() => {
    let vigente = true;
    listarImportacionesDiscord(10)
      .then(({ items }) => {
        if (!vigente || items.length === 0) return;
        const elegida = items.find((i) => ACTIVA.includes(i.estado)) ?? null;
        if (elegida) {
          setImportacion(elegida);
          setCanalId(elegida.canal_id);
          setAbierto(true);
        }
      })
      .catch(() => {
        // Sin permiso o sin configuración: el panel sigue disponible y mostrará el error al usarlo.
      });
    return () => { vigente = false; };
  }, []);

  // Polling automático mientras la importación esté pendiente o ejecutando
  useEffect(() => {
    if (!importacion) return;
    if (importacion.estado !== 'pendiente' && importacion.estado !== 'ejecutando') return;

    const timer = setInterval(async () => {
      try {
        const actualizada = await consultarImportacionDiscord(importacion.id);
        setImportacion(actualizada);
        if (actualizada.estado === 'completada' || actualizada.estado === 'completada_con_limite') {
          const resMsgs = await obtenerMensajesImportacionDiscord(actualizada.id, 20, 0);
          setMensajes(resMsgs.items);
          setTotalMensajes(resMsgs.total);
        }
      } catch {
        // Silencioso durante polling
      }
    }, 3000);

    return () => clearInterval(timer);
  }, [importacion]);

  const manejarVerificar = async () => {
    setCargandoAccion('verificar');
    setError(null);
    try {
      const res = await verificarCanalDiscord(canalId);
      setVerificacion(res);
    } catch (e) {
      const err = describirError(e);
      setError(`${err.titulo}: ${err.mensaje}`);
    } finally {
      setCargandoAccion(null);
    }
  };

  const manejarPrevisualizar = async () => {
    setCargandoAccion('previsualizar');
    setError(null);
    try {
      const res = await previsualizarDiscordHistorico({
        canal_id: canalId.trim(),
        desde,
        hasta,
        zona,
        incluir_muestra: incluirMuestra,
      });
      setPreview(res);
      setVerificacion(res);
      setClaveIntento(nuevaClave());
    } catch (e) {
      const err = describirError(e);
      setError(`${err.titulo}: ${err.mensaje}`);
    } finally {
      setCargandoAccion(null);
    }
  };

  const manejarImportar = async () => {
    if (!preview) return;
    setCargandoAccion('importar');
    setError(null);
    try {
      // alcance_congelado congela el corte exacto; la clave identifica este intento (reintentos seguros).
      const claveIdempotencia = `imp-${claveIntento || nuevaClave()}`;
      const res = await crearImportacionDiscord(
        {
          canal_id: canalId.trim(),
          desde: preview.alcance_congelado.desde,
          hasta: preview.alcance_congelado.hasta,
          zona: preview.alcance_congelado.zona,
          confirmar_alcance: confirmarAlcance,
        },
        claveIdempotencia
      );
      setImportacion(res.importacion);
      setMensajes([]);
    } catch (e) {
      const err = describirError(e);
      setError(`${err.titulo}: ${err.mensaje}`);
    } finally {
      setCargandoAccion(null);
    }
  };

  const manejarCancelar = async () => {
    if (!importacion) return;
    setCargandoAccion('cancelar');
    setError(null);
    try {
      const res = await cancelarImportacionDiscord(importacion.id);
      setImportacion(res);
    } catch (e) {
      const err = describirError(e);
      setError(`${err.titulo}: ${err.mensaje}`);
    } finally {
      setCargandoAccion(null);
    }
  };

  const manejarReanudar = async () => {
    if (!importacion) return;
    setCargandoAccion('reanudar');
    setError(null);
    try {
      const res = await reanudarImportacionDiscord(importacion.id);
      setImportacion(res);
    } catch (e) {
      const err = describirError(e);
      setError(`${err.titulo}: ${err.mensaje}`);
    } finally {
      setCargandoAccion(null);
    }
  };

  const cargarMensajesImportados = async () => {
    if (!importacion) return;
    setCargandoAccion('mensajes');
    try {
      const res = await obtenerMensajesImportacionDiscord(importacion.id, 50, 0);
      setMensajes(res.items);
      setTotalMensajes(res.total);
    } catch (e) {
      const err = describirError(e);
      setError(`${err.titulo}: ${err.mensaje}`);
    } finally {
      setCargandoAccion(null);
    }
  };

  return (
    <div className="card p-6 mt-6 border border-border">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="badge-violet mb-2 inline-flex items-center gap-1.5">
            <MessageSquare className="w-3.5 h-3.5" /> Historial de Discord
          </span>
          <h2 className="text-lg font-bold text-foreground">
            Importación histórica de Discord por canal y fechas
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            Verifica permisos, previsualiza el volumen e importa mensajes históricos a tablas protegidas (sin llamar a Gemini ni publicar).
          </p>
        </div>

        <button
          type="button"
          onClick={() => setAbierto(!abierto)}
          className="btn-primary flex items-center gap-2"
        >
          <MessageSquare className="w-4 h-4" />
          {abierto ? 'Ocultar panel Discord' : 'Abrir importador de Discord'}
        </button>
      </div>

      {abierto && (
        <div className="mt-6 pt-6 border-t border-border space-y-6">
          {/* Formulario de Canal y Fechas */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-subtle-foreground mb-1.5">
                ID del Canal (Snowflake)
              </label>
              <div className="relative">
                <Hash className="w-4 h-4 text-muted-foreground absolute left-3 top-2.5" />
                <input
                  type="text"
                  value={canalId}
                  onChange={(e) => setCanalId(e.target.value)}
                  placeholder="Ej. 222222222222222222"
                  className="input pl-9!"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-subtle-foreground mb-1.5">
                Desde (Fecha local)
              </label>
              <div className="relative">
                <Calendar className="w-4 h-4 text-muted-foreground absolute left-3 top-2.5" />
                <input
                  type="date"
                  value={desde}
                  onChange={(e) => setDesde(e.target.value)}
                  className="input pl-9!"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-subtle-foreground mb-1.5">
                Hasta (Día completo)
              </label>
              <div className="relative">
                <Calendar className="w-4 h-4 text-muted-foreground absolute left-3 top-2.5" />
                <input
                  type="date"
                  value={hasta}
                  onChange={(e) => setHasta(e.target.value)}
                  className="input pl-9!"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-subtle-foreground mb-1.5">
                Zona Horaria (IANA)
              </label>
              <input
                type="text"
                value={zona}
                onChange={(e) => setZona(e.target.value)}
                placeholder="America/Guatemala"
                className="input"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={incluirMuestra}
                onChange={(e) => setIncluirMuestra(e.target.checked)}
              />
              Incluir muestra de hasta 5 mensajes en la previsualización
            </label>

            <div className="flex flex-wrap gap-3 ml-auto">
              <button
                type="button"
                onClick={manejarVerificar}
                disabled={cargandoAccion !== null || !canalId.trim()}
                className="btn-secondary text-xs"
              >
                {cargandoAccion === 'verificar' ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <CheckCircle2 className="w-4 h-4 text-success" />
                )}
                1. Verificar canal
              </button>

              <button
                type="button"
                onClick={manejarPrevisualizar}
                disabled={cargandoAccion !== null || !canalId.trim() || !desde || !hasta}
                className="btn-info-soft text-xs"
              >
                {cargandoAccion === 'previsualizar' ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Eye className="w-4 h-4" />
                )}
                2. Previsualizar rango
              </button>
            </div>
          </div>

          {error && (
            <div role="alert" className="p-3.5 rounded-xl bg-danger-soft text-danger text-xs font-medium flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Resultado de Verificación */}
          {verificacion && (
            <div className="p-4 rounded-xl bg-surface-muted/50 border border-border text-xs space-y-1.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-bold text-foreground">
                  Servidor: {verificacion.servidor.nombre} · Canal: #{verificacion.canal.nombre} ({verificacion.canal.tipo_nombre})
                </span>
                <span className="badge-success">Canal Autorizado y Accesible</span>
              </div>
              <p className="text-muted-foreground">
                Permisos del bot: Ver canal ({verificacion.permisos.ver_canal ? 'Sí' : 'No'}) · Leer historial ({verificacion.permisos.leer_historial ? 'Sí' : 'No'})
              </p>
            </div>
          )}

          {/* Resultado de Previsualización */}
          {preview && (
            <div className="p-5 rounded-xl border border-border bg-surface space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-bold text-foreground">Previsualización del alcance</h3>
                  <p className="text-xs text-muted-foreground">
                    Rango congelado (UTC): {preview.alcance_congelado.desde} → {preview.alcance_congelado.hasta} ({preview.rango.dias} días)
                  </p>
                </div>

                <div className="text-right">
                  {preview.conteo.tipo === 'exacto' ? (
                    <span className="badge-info">
                      Conteo exacto: {preview.conteo.importables} importables (de {preview.conteo.mensajes_en_rango})
                    </span>
                  ) : (
                    <span className="badge-warning">
                      Estimado: ~{preview.conteo.estimacion_aproximada ?? preview.conteo.minimo} mensajes (mín. {preview.conteo.minimo})
                    </span>
                  )}
                </div>
              </div>

              {preview.advertencias.length > 0 && (
                <div className="text-xs text-subtle-foreground space-y-1">
                  <p className="font-semibold text-foreground">Notas del alcance:</p>
                  <ul className="list-disc list-inside">
                    {preview.advertencias.map((adv) => (
                      <li key={adv}>{adv}</li>
                    ))}
                  </ul>
                </div>
              )}

              {preview.muestra && preview.muestra.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-foreground">Muestra preliminar:</p>
                  <div className="space-y-1.5 max-h-40 overflow-y-auto">
                    {preview.muestra.map((m) => (
                      <div key={m.id_mensaje} className="p-2 rounded-lg bg-surface-muted text-xs flex justify-between gap-3">
                        <span className="text-foreground truncate">{m.texto || '(sin texto)'}</span>
                        <span className="text-subtle-foreground font-mono shrink-0">{new Date(m.fecha).toLocaleDateString()}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="pt-3 border-t border-border flex flex-wrap items-center justify-between gap-4">
                {preview.limites.requiere_confirmacion && (
                  <label className="flex items-center gap-2 text-xs text-warning font-semibold cursor-pointer">
                    <input
                      type="checkbox"
                      checked={confirmarAlcance}
                      onChange={(e) => setConfirmarAlcance(e.target.checked)}
                    />
                    Confirmo que el rango supera el umbral ({preview.limites.umbral_confirmacion.dias} días / {preview.limites.umbral_confirmacion.mensajes} mensajes)
                  </label>
                )}

                <button
                  type="button"
                  onClick={manejarImportar}
                  disabled={
                    cargandoAccion !== null ||
                    (preview.limites.requiere_confirmacion && !confirmarAlcance)
                  }
                  className="btn-success text-xs ml-auto flex items-center gap-2"
                >
                  {cargandoAccion === 'importar' ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Download className="w-4 h-4" />
                  )}
                  3. Confirmar e importar historial
                </button>
              </div>
            </div>
          )}

          {/* Estado y Progreso de la Importación */}
          {importacion && (
            <div className="p-5 rounded-xl border border-border bg-surface-muted/30 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="font-mono text-xs text-subtle-foreground">{importacion.id}</span>
                  <h3 className="text-sm font-bold text-foreground">
                    Estado de la importación: <span className="uppercase text-primary">{importacion.estado}</span>
                  </h3>
                </div>

                <div className="flex items-center gap-2">
                  {(importacion.estado === 'pendiente' || importacion.estado === 'ejecutando') && (
                    <button
                      type="button"
                      onClick={manejarCancelar}
                      disabled={cargandoAccion !== null}
                      className="btn-danger-soft text-xs"
                    >
                      <XCircle className="w-4 h-4" /> Cancelar
                    </button>
                  )}

                  {importacion.estado === 'error' && importacion.error?.reanudable && (
                    <button
                      type="button"
                      onClick={manejarReanudar}
                      disabled={cargandoAccion !== null}
                      className="btn-info-soft text-xs"
                    >
                      <RotateCcw className="w-4 h-4" /> Reanudar
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={cargarMensajesImportados}
                    disabled={cargandoAccion !== null}
                    className="btn-secondary text-xs"
                  >
                    Ver mensajes importados ({importacion.insertados + importacion.existentes})
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div className="p-3 rounded-lg bg-surface border border-border">
                  <span className="text-subtle-foreground block">Páginas leídas</span>
                  <span className="text-base font-bold text-foreground tabular-nums">{importacion.paginas}</span>
                </div>
                <div className="p-3 rounded-lg bg-surface border border-border">
                  <span className="text-subtle-foreground block">Nuevos insertados</span>
                  <span className="text-base font-bold text-success tabular-nums">{importacion.insertados}</span>
                </div>
                <div className="p-3 rounded-lg bg-surface border border-border">
                  <span className="text-subtle-foreground block">Ya existentes</span>
                  <span className="text-base font-bold text-foreground tabular-nums">
                    {importacion.existentes + importacion.existentes_en_vivo}
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-surface border border-border">
                  <span className="text-subtle-foreground block">Examinados en rango</span>
                  <span className="text-base font-bold text-foreground tabular-nums">{importacion.en_rango}</span>
                </div>
              </div>

              {mensajes.length > 0 && (
                <div className="pt-3 border-t border-border space-y-2">
                  <p className="text-xs font-bold text-foreground">
                    Mensajes importados ({mensajes.length} de {totalMensajes}):
                  </p>
                  <div className="max-h-60 overflow-y-auto space-y-1.5">
                    {mensajes.map((m) => (
                      <div key={m.id_mensaje} className="p-2.5 rounded-lg bg-surface border border-border text-xs flex justify-between gap-4">
                        <div>
                          <span className="font-mono text-[11px] text-primary">{m.id_mensaje}</span>
                          <p className="text-foreground mt-0.5">{m.texto || '(sin contenido de texto)'}</p>
                        </div>
                        <div className="text-right shrink-0">
                          <span className={m.estado_ia === 'procesado' ? 'badge-success' : 'badge-neutral'}>
                            {ETIQUETA_IA[m.estado_ia ?? 'sin_evidencia'] ?? m.estado_ia}
                          </span>
                          <p className="text-[11px] text-subtle-foreground mt-1">
                            {new Date(m.fecha).toLocaleString()}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
