'use client';


import UiTree from '@/components/UiTree';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import {
  UploadCloud, FileJson, CheckCircle2, AlertCircle, Loader2, Clock, XCircle, RefreshCw,
  ArrowRight, Info, AlertTriangle,
} from 'lucide-react';
import { motion } from 'framer-motion';
import {
  subirLote, consultarTrabajo, describirError,
  ErrorLegible, EstadoTrabajo, RespuestaSubida, Trabajo,
} from '@/services/api';
import Sidebar from '@/components/Sidebar';
import ConectarDiscord from '@/components/ConectarDiscord';
import PendientesDiscord from '@/components/PendientesDiscord';
import RutaProtegida from '@/components/RutaProtegida';
import { detectarMetadatosArchivo } from '@/utils/metadatosArchivo';

const MAX_BYTES = 5 * 1024 * 1024;
const EXTENSIONES = ['.json', '.jsonl', '.csv'];
// Consulta rápida al inicio y más espaciada después; se detiene en estados finales.
const intervaloConsulta = (transcurridoMs: number) => (transcurridoMs < 30_000 ? 2_000 : 5_000);
const ESPERA_PROLONGADA_MS = 120_000;
const MAX_FALLOS_CONSULTA = 5;

const ETIQUETA_ESTADO: Record<EstadoTrabajo, string> = {
  recibido: 'En cola',
  procesando: 'Procesando',
  terminado: 'Terminado',
  error: 'Con error',
};

const MENSAJE_ERROR_TRABAJO: Record<string, string> = {
  ia_configuracion: 'El proveedor de IA rechazó la solicitud (configuración o petición inválida).',
  ia_cuota: 'Se alcanzó el límite de uso del proveedor de IA. Inténtalo más tarde.',
  ia_transitorio: 'El proveedor de IA no respondió a tiempo. Puedes reintentar más tarde.',
  ia_respuesta_invalida: 'La IA devolvió respuestas que no cumplen el formato esperado.',
  ia_bloqueado: 'El proveedor de IA bloqueó el contenido por sus filtros de seguridad.',
  ia_presupuesto: 'El lote superó el presupuesto de tiempo, llamadas o tokens del trabajo.',
  timeout: 'El procesamiento superó el tiempo máximo del trabajo.',
  reserva_agotada: 'El trabajo se interrumpió varias veces y quedó detenido.',
};

export default function IngestaPage() {
  const [origen, setOrigen] = useState('');
  const [periodo, setPeriodo] = useState('');
  const [cierre, setCierre] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [errorArchivo, setErrorArchivo] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [errorEnvio, setErrorEnvio] = useState<ErrorLegible | null>(null);
  const [subida, setSubida] = useState<RespuestaSubida | null>(null);
  const [trabajo, setTrabajo] = useState<Trabajo | null>(null);
  const [errorConsulta, setErrorConsulta] = useState<string | null>(null);
  const [esperaProlongada, setEsperaProlongada] = useState(false);
  const [intentoConsulta, setIntentoConsulta] = useState(0);
  const enviandoRef = useRef(false);
  const lecturaArchivo = useRef(0);

  const estado: EstadoTrabajo | null = trabajo?.estado ?? subida?.estado ?? null;
  const final = estado === 'terminado' || estado === 'error';
  // Solo el estado consultado detiene el seguimiento: un trabajo reutilizado que ya terminó
  // se consulta una vez para mostrar su resultado.
  const trabajoFinal = trabajo?.estado === 'terminado' || trabajo?.estado === 'error';

  // Seguimiento del trabajo: se detiene al terminar, fallar, salir de la pantalla o tras fallos de red.
  useEffect(() => {
    if (!subida || trabajoFinal) return;
    let vigente = true;
    let temporizador: ReturnType<typeof setTimeout> | undefined;
    const controlador = new AbortController();
    const inicio = Date.now();
    let fallos = 0;

    const consultar = async () => {
      try {
        const actual = await consultarTrabajo(subida.procesamiento_id, controlador.signal);
        if (!vigente) return;
        fallos = 0;
        setErrorConsulta(null);
        setTrabajo(actual);
        if (actual.estado === 'terminado' || actual.estado === 'error') return;
      } catch (error) {
        if (!vigente) return;
        fallos += 1;
        if (fallos >= MAX_FALLOS_CONSULTA) {
          setErrorConsulta(describirError(error).mensaje);
          return;
        }
      }
      const transcurrido = Date.now() - inicio;
      setEsperaProlongada(transcurrido > ESPERA_PROLONGADA_MS);
      temporizador = setTimeout(consultar, intervaloConsulta(transcurrido) * (fallos ? 2 ** fallos : 1));
    };
    consultar();
    return () => {
      vigente = false;
      controlador.abort();
      if (temporizador) clearTimeout(temporizador);
    };
  }, [subida, trabajoFinal, intentoConsulta]);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validarYGuardarArchivo(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      validarYGuardarArchivo(e.target.files[0]);
    }
    e.target.value = '';
  };

  const reiniciar = () => {
    setSubida(null);
    setTrabajo(null);
    setErrorEnvio(null);
    setErrorConsulta(null);
    setEsperaProlongada(false);
  };

  const validarYGuardarArchivo = async (archivo: File) => {
    if (enviandoRef.current || (subida && !final)) return;
    const lectura = ++lecturaArchivo.current;
    setOrigen(''); setPeriodo(''); setFile(null);
    const nombre = archivo.name.toLowerCase();
    reiniciar();
    if (!EXTENSIONES.some((ext) => nombre.endsWith(ext))) {
      setFile(null);
      setErrorArchivo('Formato no soportado: sube un archivo .json, .jsonl o .csv.');
      return;
    }
    if (archivo.size > MAX_BYTES) {
      setFile(null);
      setErrorArchivo(`El archivo pesa ${(archivo.size / 1024 / 1024).toFixed(1)} MiB; el máximo es 5 MiB.`);
      return;
    }
    setErrorArchivo(null);
    try {
      const metadatos = detectarMetadatosArchivo(archivo.name, await archivo.text());
      if (lectura !== lecturaArchivo.current) return;
      setOrigen(metadatos.nombre.slice(0, 200));
      setPeriodo(metadatos.periodo.slice(0, 100));
      setFile(archivo);
    } catch {
      if (lectura !== lecturaArchivo.current) return;
      setErrorArchivo('No se pudo leer el archivo. Revisa su estructura y formato.');
    }
  };

  const procesarLote = async () => {
    // El ref evita dobles envíos por doble clic antes de que React vuelva a renderizar.
    if (!file || enviandoRef.current || !origen.trim() || !periodo.trim()) return;
    enviandoRef.current = true;
    setEnviando(true);
    reiniciar();
    try {
      setSubida(await subirLote(file, origen.trim(), periodo.trim(), cierre));
    } catch (error) {
      setErrorEnvio(describirError(error));
    } finally {
      enviandoRef.current = false;
      setEnviando(false);
    }
  };

  const activos = trabajo?.resultado?.activos_distribucion_generados ?? [];
  const advertencias = activos.reduce((n, a) => n + (a.advertencias_fidelidad?.length ?? 0), 0);
  const duracion = trabajo && final
    ? Math.max(0, (new Date(trabajo.actualizado).getTime() - new Date(trabajo.creado).getTime()) / 1000)
    : null;
  const botonDeshabilitado = !file || enviando || (!!subida && !final) || !origen.trim() || !periodo.trim();

  return <UiTree>{(
    <RutaProtegida>
      <div className="flex min-h-screen w-full">
        <Sidebar />

        <main className="dashboard-content flex-1 min-w-0 p-4 sm:p-6 md:p-10">
          <header className="ingestion-heading mb-8 flex items-center gap-3">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground">
              Ingesta de datos
            </h1>
          </header>

          <div className="ingestion-panels grid gap-6 items-stretch">
            <div id="conectar-discord" className="ingestion-discord min-w-0 scroll-mt-20">
              <ConectarDiscord />
            </div>
            <div className="ingestion-source card p-5 sm:p-7 min-w-0">
              <div className="mb-6">
                <h2 className="text-[15px] font-semibold text-foreground">Fuente de datos</h2>
                <p className="ingestion-classifier-note mt-3">
                  El nombre y el período se utilizan para clasificar el lote.
                </p>
              </div>

              <div className="grid gap-4 sm:grid-cols-2 mb-4">
                <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground">
                  Nombre
                  <input className="input" value={origen} maxLength={200} onChange={(e) => setOrigen(e.target.value)} />
                </label>
                <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground">
                  Período
                  <input className="input" value={periodo} maxLength={100} placeholder="" onChange={(e) => setPeriodo(e.target.value)} />
                </label>
              </div>

              <label className="flex items-center gap-2.5 text-sm text-foreground mb-5 cursor-pointer w-fit">
                <input
                  type="checkbox"
                  className="w-4 h-4 accent-primary"
                  checked={cierre}
                  onChange={(e) => setCierre(e.target.checked)}
                />
                Cerrar período y generar resumen
              </label>

              <form onDragEnter={handleDrag} onSubmit={(e) => e.preventDefault()}>
                <input
                  type="file"
                  id="file-upload"
                  className="hidden"
                  accept=".json,.jsonl,.csv"
                  onChange={handleChange}
                />
                <label
                  htmlFor="file-upload"
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                  className={`flex flex-col items-center justify-center w-full h-52 sm:h-60 border-2 border-dashed rounded-2xl cursor-pointer transition-all duration-200 ${
                    dragActive
                      ? 'border-primary bg-primary-soft scale-[1.01]'
                      : file
                      ? 'border-success/50 bg-success-soft'
                      : 'border-border-strong hover:border-primary/60 hover:bg-surface-hover'
                  }`}
                >
                  <div className="flex flex-col items-center justify-center px-6 text-center min-w-0 max-w-full">
                    {file ? (
                      <motion.div
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="flex flex-col items-center min-w-0 max-w-full"
                      >
                        <div className="w-16 h-16 rounded-full bg-surface border border-success/30 flex items-center justify-center mb-4 shadow-sm">
                          <FileJson className="w-8 h-8 text-success" />
                        </div>
                        <p className="mb-1.5 text-[15px] font-medium text-foreground">
                          Archivo listo para procesar
                        </p>
                        <p className="badge-success font-mono max-w-full truncate">
                          {file.name} · {(file.size / 1024).toFixed(2)} KB
                        </p>
                      </motion.div>
                    ) : (
                      <>
                        <div
                          className={`w-16 h-16 rounded-full flex items-center justify-center mb-4 transition-colors ${
                            dragActive
                              ? 'bg-surface border border-primary/40'
                              : 'bg-surface-muted border border-border'
                          }`}
                        >
                          <UploadCloud
                            className={`w-8 h-8 ${dragActive ? 'text-primary' : 'text-subtle-foreground'}`}
                          />
                        </div>
                        <p className="mb-1.5 text-[15px] text-muted-foreground">
                          <span className="font-semibold text-primary">Haz clic para subir</span> o arrastra y suelta
                        </p>
                        <p className="text-xs text-subtle-foreground">JSON, JSONL o CSV · máx. 5 MiB · 500 registros</p>
                      </>
                    )}
                  </div>
                </label>
              </form>

              {errorArchivo && (
                <p role="alert" className="mt-3 text-sm text-danger flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" /> {errorArchivo}
                </p>
              )}

              {errorEnvio && (
                <div role="alert" className="mt-4 rounded-xl border border-danger/30 bg-danger-soft p-4 text-sm">
                  <p className="font-semibold text-danger flex items-center gap-2">
                    <XCircle className="w-4 h-4 shrink-0" /> {errorEnvio.titulo}
                  </p>
                  <p className="mt-1 text-foreground">{errorEnvio.mensaje}</p>
                  {errorEnvio.errores.length > 0 && (
                    <ul className="mt-2 space-y-1 text-muted-foreground">
                      {errorEnvio.errores.map((e, i) => (
                        <li key={i}>
                          {e.registro ? `Registro ${e.registro}` : 'Lote'}
                          {e.id ? ` (id ${e.id})` : ''}
                          {e.campo ? ` · ${e.campo}` : ''}: {e.motivo}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              <div className="mt-7 pt-6 flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-2.5 text-sm min-w-0" role="status" aria-live="polite">
                  {enviando && (
                    <span className="flex items-center gap-2.5 text-primary">
                      <Loader2 className="w-4 h-4 animate-spin" /> Enviando archivo…
                    </span>
                  )}
                  {!enviando && trabajo?.estado === 'terminado' && (
                    <span className="flex items-center gap-2 text-foreground">
                      <CheckCircle2 className="w-4 h-4 text-[#23a094] fill-none" aria-hidden="true" /> Ingesta completada
                    </span>
                  )}
                  {!enviando && subida && !trabajoFinal && (
                    <span className="flex items-center gap-2 text-muted-foreground">
                      <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" /> Procesando datos…
                    </span>
                  )}
                  {!enviando && trabajo?.estado === 'error' && (
                    <span className="flex items-center gap-2 text-danger">
                      <XCircle className="w-4 h-4" aria-hidden="true" /> La ingesta no se completó
                    </span>
                  )}
                  {!enviando && !subida && !file && (
                    <span className="flex items-center gap-2 text-subtle-foreground">
                      <AlertCircle className="w-4 h-4 text-[#f1f333] fill-none" aria-hidden="true" /> Esperando archivo
                    </span>
                  )}
                  {!enviando && !subida && file && !errorEnvio && (
                    <span className="flex items-center gap-2 text-subtle-foreground">
                      <Info className="w-4 h-4" /> Listo para iniciar
                    </span>
                  )}
                </div>

                <div className="flex gap-2.5">
                  {final && (
                    <button onClick={reiniciar} className="btn-secondary">
                      Nuevo envío
                    </button>
                  )}
                  <button
                    onClick={procesarLote}
                    disabled={botonDeshabilitado}
                    className={botonDeshabilitado ? 'btn-secondary' : 'btn-primary'}
                  >
                    {enviando ? 'Enviando…' : subida && !final ? 'En seguimiento…' : 'Iniciar procesamiento'}
                  </button>
                </div>
              </div>
            </div>

            <div className="ingestion-support grid gap-6 min-w-0 items-stretch">
              {subida && estado && (
                <section aria-live="polite" className="ingestion-tracking card p-5 sm:p-6 min-w-0">
                  <h2 className="text-[15px] font-semibold text-foreground mb-1">Seguimiento del trabajo</h2>
                  <p className="text-xs text-muted-foreground font-mono break-all mb-4">{subida.procesamiento_id}</p>

                  {subida.reutilizado && (
                    <p className="badge-info mb-4 w-fit">Este lote ya existía: se muestra el trabajo registrado</p>
                  )}

                  <ol className="flex flex-col gap-3 text-sm">
                    {(['recibido', 'procesando', 'terminado'] as const).map((paso, indice) => {
                      const orden = { recibido: 0, procesando: 1, terminado: 2, error: 2 }[estado];
                      const hecho = orden > indice || (estado === 'terminado' && paso === 'terminado');
                      const actual = orden === indice && !final;
                      const fallo = estado === 'error' && paso === 'terminado';
                      return <UiTree key={paso}>{(
                        <li key={paso} className="flex items-center gap-2.5">
                          {fallo ? <XCircle className="w-4 h-4 text-danger" />
                            : hecho ? <CheckCircle2 className="w-4 h-4 text-success" />
                            : actual ? <Loader2 className="w-4 h-4 animate-spin text-primary" />
                            : <Clock className="w-4 h-4 text-subtle-foreground" />}
                          <span className={actual ? 'text-foreground font-medium' : hecho ? 'text-foreground' : 'text-subtle-foreground'}>
                            {fallo ? 'Error' : ETIQUETA_ESTADO[paso]}
                          </span>
                        </li>
                      )}</UiTree>;
                    })}
                  </ol>

                  <p className="mt-4 text-xs text-muted-foreground">
                    {subida.interacciones} interacciones
                    {subida.registros_duplicados_omitidos > 0 && ` · ${subida.registros_duplicados_omitidos} duplicadas omitidas`}
                  </p>
                  {subida.metadatos_archivo_ignorados.length > 0 && (
                    <p className="mt-1 text-xs text-warning">
                      Se usaron los valores del formulario en lugar de: {subida.metadatos_archivo_ignorados.join(', ')} del archivo.
                    </p>
                  )}

                  {esperaProlongada && !final && !errorConsulta && (
                    <p className="mt-4 text-xs text-warning flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      Está tardando más de lo habitual. El trabajo sigue registrado; puedes volver más tarde con este ID.
                    </p>
                  )}

                  {errorConsulta && (
                    <div className="mt-4 text-xs text-danger flex flex-wrap items-center gap-2">
                      <span>No se pudo consultar el estado: {errorConsulta}</span>
                      <button onClick={() => { setErrorConsulta(null); setIntentoConsulta((n) => n + 1); }} className="btn-secondary px-2.5! py-1.5!">
                        <RefreshCw className="w-3.5 h-3.5" /> Reintentar consulta
                      </button>
                    </div>
                  )}

                  {estado === 'terminado' && trabajo && (
                    <div className="mt-5 pt-4 border-t border-border text-sm flex flex-col gap-2">
                      <p className="text-foreground">
                        <strong>{activos.length}</strong> contenidos generados ·{' '}
                        <strong>{trabajo.resultado?.alertas_internas?.length ?? 0}</strong> alertas internas
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {trabajo.resultado?.simulado ? 'Modo simulado (sin IA real)' : 'Procesado con IA'}
                        {duracion !== null && ` · ${duracion.toFixed(1)} s desde el registro`}
                        {trabajo.resultado?.persistencia?.postgres === 'guardado' && ' · guardado en la base de datos'}
                      </p>
                      {advertencias > 0 && (
                        <p className="text-xs text-warning">
                          {advertencias} advertencia(s) de fidelidad para revisar en curaduría.
                        </p>
                      )}
                      <p className="text-xs text-subtle-foreground">
                        Las alertas internas no se publican. Ningún contenido se publica sin revisión humana.
                      </p>
                      <Link href={`/curaduria?trabajo=${encodeURIComponent(trabajo.id)}`} className="btn-primary w-fit mt-1">
                        Ver resultados en curaduría <ArrowRight className="w-4 h-4" />
                      </Link>
                    </div>
                  )}

                  {estado === 'error' && (
                    <div className="mt-5 pt-4 border-t border-border text-sm">
                      <p className="text-danger font-medium">
                        {MENSAJE_ERROR_TRABAJO[trabajo?.error_codigo ?? ''] ?? 'El procesamiento terminó con error.'}
                      </p>
                      {trabajo?.resultado?.diagnostico && (
                        <p className="text-xs text-muted-foreground mt-1">
                          Diagnóstico: HTTP {trabajo.resultado.diagnostico.http} · {trabajo.resultado.diagnostico.categoria}
                          {trabajo.resultado.diagnostico.detalle ? ` · ${trabajo.resultado.diagnostico.detalle}` : ''}
                        </p>
                      )}
                      <p className="text-xs text-subtle-foreground mt-1">Código: {trabajo?.error_codigo ?? 'desconocido'}</p>
                    </div>
                  )}
                </section>
              )}



              <PendientesDiscord />
              <section className="ingestion-requirements card p-5 sm:p-6 min-w-0" aria-labelledby="ingestion-requisitos-titulo"><h2 id="ingestion-requisitos-titulo" className="text-[15px] font-semibold text-foreground mb-4 flex items-center gap-2"><AlertCircle className="w-4 h-4 shrink-0 text-[#f1f333] fill-none warning-outline" aria-hidden="true" />Formatos y requisitos</h2>
                <ul className="list-disc pl-5 space-y-3 text-sm">
                  <li><strong>Formatos:</strong> <code>.json</code> (lista o <code>{'{"interacciones": [...]}'}</code>), <code>.jsonl</code> o <code>.csv</code> con encabezado, en UTF-8.</li>
                  <li><strong>Campos obligatorios:</strong> <code>id</code> (o <code>id_mensaje</code>), <code>autor</code>, <code>canal</code>, <code>fecha</code> y <code>texto</code>. <code>tipo</code> es opcional.</li>
                  <li><strong>Fecha:</strong> ISO 8601 con hora y zona, por ejemplo, <code>2026-10-19T14:10:00Z</code>.</li>
                  <li><strong>Límites:</strong> 5 MiB; 500 registros; <code>autor</code>: 150 caracteres; <code>canal</code> y <code>tipo</code>: 50.</li>
                  <li><strong>Repetidos:</strong> los idénticos se omiten; el mismo <code>id</code> con otro contenido es un error.</li>
                  <li><strong>Si hay un error, no se procesa nada:</strong> verás la lista de problemas para corregirlos.</li>
                  <li><strong>Reenviar el mismo archivo</strong> con el mismo nombre y período no lo procesa dos veces.</li>
                </ul></section>


            </div>
          </div>
        </main>
      </div>
    </RutaProtegida>
  )}</UiTree>;
}