'use client';

import { useState } from 'react';
import { UploadCloud, FileJson, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { subirLote } from '@/services/api';
import Sidebar from '@/components/Sidebar';

export default function IngestaPage() {
  const [origen, setOrigen] = useState('panel_local');
  const [periodo, setPeriodo] = useState('Semana 2');
  const [cierre, setCierre] = useState(false);
  const [trabajoId, setTrabajoId] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [procesando, setProcesando] = useState(false);
  const [completado, setCompletado] = useState(false);

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
  };

  const validarYGuardarArchivo = (archivo: File) => {
    if (
      archivo.type === 'application/json' ||
      archivo.name.endsWith('.jsonl') ||
      archivo.name.endsWith('.csv') ||
      archivo.name.endsWith('.json')
    ) {
      setFile(archivo);
      setCompletado(false);
    } else {
      alert('Por favor, sube únicamente archivos JSON o CSV.');
    }
  };

  const procesarLote = async () => {
    if (!file) return;
    setProcesando(true);

    try {
      const respuesta = await subirLote(file, origen, periodo, cierre);
      console.log('Respuesta del servidor:', respuesta);
      setProcesando(false);
      setTrabajoId(respuesta.procesamiento_id);
      setCompletado(true);
    } catch (error) {
      console.error('Error subiendo el archivo:', error);
      alert('Hubo un error al procesar el archivo. Revisa la consola.');
      setProcesando(false);
    }
  };

  const botonDeshabilitado = !file || procesando || completado;

  return (
    <div className="flex min-h-screen w-full">
      <Sidebar />

      <main className="flex-1 min-w-0 p-6 md:p-10">
        <header className="mb-8">
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
            Ingesta de lotes
          </h1>
          <p className="text-muted-foreground mt-1.5 text-[15px]">
            Sube archivos JSON o CSV para procesarlos mediante los agentes de IA.
          </p>
        </header>

        <div className="card max-w-2xl p-7">
          <div className="mb-6">
            <h2 className="text-[15px] font-semibold text-foreground">Fuente de datos</h2>
            <p className="text-sm text-muted-foreground mt-1">
              El esquema del dataset se normaliza automáticamente antes de entrar al pipeline.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 mb-4">
            <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground">
              Comunidad
              <input className="input" value={origen} onChange={(e) => setOrigen(e.target.value)} />
            </label>
            <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground">
              Período
              <input className="input" value={periodo} onChange={(e) => setPeriodo(e.target.value)} />
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
              className={`flex flex-col items-center justify-center w-full h-60 border-2 border-dashed rounded-2xl cursor-pointer transition-all duration-200 ${
                dragActive
                  ? 'border-primary bg-primary-soft scale-[1.01]'
                  : file
                  ? 'border-success/50 bg-success-soft'
                  : 'border-border-strong hover:border-primary/60 hover:bg-surface-hover'
              }`}
            >
              <div className="flex flex-col items-center justify-center px-6 text-center">
                {file ? (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="flex flex-col items-center"
                  >
                    <div className="w-16 h-16 rounded-full bg-surface border border-success/30 flex items-center justify-center mb-4 shadow-sm">
                      <FileJson className="w-8 h-8 text-success" />
                    </div>
                    <p className="mb-1.5 text-[15px] font-medium text-foreground">
                      Archivo listo para procesar
                    </p>
                    <p className="badge-success font-mono">
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
                    <p className="text-xs text-subtle-foreground">Formatos soportados: JSON, JSONL, CSV</p>
                  </>
                )}
              </div>
            </label>
          </form>

          {trabajoId && (
            <p className="text-xs mt-3 text-muted-foreground">
              Trabajo: <span className="font-mono text-foreground">{trabajoId}</span>.{' '}
              <a
                className="text-primary underline underline-offset-2 hover:text-primary-hover"
                href={`/api/v1/trabajos/${trabajoId}`}
                target="_blank"
                rel="noreferrer"
              >
                Consultar estado y resultado
              </a>
            </p>
          )}

          <div className="mt-7 pt-6 border-t border-border flex items-center justify-between gap-4">
            <div className="flex items-center gap-2.5 text-sm">
              {procesando && (
                <span className="flex items-center gap-2.5 text-primary">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Procesando archivo…
                </span>
              )}
              {completado && (
                <motion.span
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-2 text-success"
                >
                  <CheckCircle2 className="w-4 h-4" /> Lote recibido; pendiente de procesamiento
                </motion.span>
              )}
              {!procesando && !completado && !file && (
                <span className="flex items-center gap-2 text-subtle-foreground">
                  <AlertCircle className="w-4 h-4" /> Esperando dataset
                </span>
              )}
            </div>

            <button
              onClick={procesarLote}
              disabled={botonDeshabilitado}
              className={botonDeshabilitado ? 'btn-secondary' : 'btn-primary'}
            >
              {procesando ? 'Procesando…' : completado ? 'Recibido' : 'Iniciar procesamiento'}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}