import axios from 'axios';

// Configuración base apuntando a tu FastAPI
export const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Tipado estricto basado en tu Pydantic del Backend
export interface Mensaje {
  id_mensaje: string;
  autor: string;
  fecha: string;
  canal: string;
  tipo: string;
  texto: string;
  sentimiento_ref?: string;
  tema_ref?: string;
}

// Reemplaza tu función obtenerMensajes por esta:

export interface PaginatedMensajes {
  items: Mensaje[];
  total: number;
}

export const obtenerMensajes = async (
  skip: number = 0, 
  limit: number = 10, 
  canal?: string,
  ambito?: Ambito | null
): Promise<PaginatedMensajes> => {
  const response = await apiClient.get('/mensajes', { 
    params: { skip, limit, canal, origen: ambito?.origen, periodo: ambito?.periodo }
  });
  return response.data;
};

export interface RespuestaSubida {
  procesamiento_id: string;
  estado: EstadoTrabajo;
  reutilizado: boolean;
  consulta: string;
  interacciones: number;
  registros_duplicados_omitidos: number;
  metadatos_archivo_ignorados: string[];
}

export const subirLote = async (
  archivo: File, origen: string, periodo: string, cierre: boolean,
): Promise<RespuestaSubida> => {
  const formData = new FormData();
  formData.append('file', archivo);
  formData.append('origen_comunidad', origen);
  formData.append('periodo_referencia', periodo);
  formData.append('cierre_periodo', String(cierre));

  const response = await apiClient.post('/mensajes/procesamientos', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

// --- Interfaces de Curaduría ---
export type EstadoActivo = 'generado' | 'revisado' | 'aprobado' | 'rechazado';
export type FormatoActivo = 'linkedin' | 'faq' | 'newsletter';

export interface FuenteMensajeDetalle {
  id_mensaje: string;
  autor: string;
  canal: string;
  fecha: string;
  texto: string;
}

export interface Activo {
  id_activo: string;
  formato: FormatoActivo;
  titulo: string;
  copy: string;
  estado: EstadoActivo;
  fuentes: string[];
  version: number;
  comentario_curador?: string;
  advertencias_fidelidad?: AdvertenciaFidelidad[] | null;
  fecha_actualizacion: string;
  fuentes_detalle?: FuenteMensajeDetalle[]; // Solo viene al pedir el detalle
}

export interface PaginatedActivosResponse {
  items: Activo[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

// --- Funciones de Curaduría ---
export const listarActivos = async (
  page: number = 1,
  limit: number = 15,
  estado?: string,
  trabajo?: string | null
): Promise<PaginatedActivosResponse> => {
  const params: Record<string, string | number> = { page, limit };
  if (estado) params.estado = estado;
  if (trabajo) params.trabajo = trabajo;
  
  const response = await apiClient.get('/curaduria/activos', { params });
  return response.data;
};

export const obtenerDetalleActivo = async (id_activo: string): Promise<Activo> => {
  const response = await apiClient.get(`/curaduria/activos/${id_activo}`);
  return response.data;
};

export const actualizarActivo = async (
  id_activo: string,
  payload: { copy?: string; estado?: string; comentario_curador?: string }
): Promise<Activo> => {
  const response = await apiClient.patch(`/curaduria/activos/${id_activo}`, payload);
  return response.data;
};

// Al final del archivo añade:

// Semántica documentada en docs/metricas-panel.md.
export interface DashboardKPIs {
  total_mensajes: number;
  mensajes_por_tipo: Record<string, number>;
  distribucion_sentimiento: { positivo: number; negativo: number; neutral: number };
  sentimiento: { estado: 'sin_datos' | 'parcial' | 'completo'; clasificados: number; sin_clasificar: number };
  activos_generados: number;
  activos_por_estado: Record<string, number>;
  borradores_pendientes: number;
  activos_aprobados: number;
  publicados: number | null;
  publicacion_externa: string;
  alertas_internas: number;
  alertas_registradas: number;
}

export interface Ambito {
  origen: string;
  periodo: string;
  trabajos?: number;
  terminados?: number;
  ultimo?: string | null;
}

export const obtenerKPIs = async (ambito?: Ambito | null): Promise<DashboardKPIs> => {
  const response = await apiClient.get('/dashboard/kpis', {
    params: { origen: ambito?.origen, periodo: ambito?.periodo },
  });
  return response.data;
};

export const obtenerAmbitos = async (): Promise<Ambito[]> => {
  const response = await apiClient.get('/dashboard/ambitos');
  return response.data.items;
};

// --- Trabajos asíncronos ---
export type EstadoTrabajo = 'recibido' | 'procesando' | 'terminado' | 'error';

export interface AdvertenciaFidelidad {
  tipo: string;
  detalle: string;
}

// Solo valores de catálogo generados por el backend; nunca texto del proveedor.
export interface DiagnosticoIA {
  http?: number | null;
  categoria?: string;
  estado_proveedor?: string | null;
  razon?: string | null;
  detalle?: string;
}

export interface Trabajo {
  id: string;
  estado: EstadoTrabajo;
  intentos: number;
  error_codigo: string | null;
  historial: EstadoTrabajo[];
  creado: string;
  actualizado: string;
  resultado: {
    simulado?: boolean;
    activos_distribucion_generados?: { advertencias_fidelidad?: AdvertenciaFidelidad[] }[];
    alertas_internas?: unknown[];
    persistencia?: { postgres: string; activos: number };
    diagnostico?: DiagnosticoIA;
  } | null;
}

export const consultarTrabajo = async (id: string, signal?: AbortSignal): Promise<Trabajo> => {
  const response = await apiClient.get(`/v1/trabajos/${encodeURIComponent(id)}`, { signal, timeout: 15000 });
  return response.data;
};

// --- Errores legibles y seguros ---
export type TipoError = 'validacion' | 'tamano' | 'conflicto' | 'formato' | 'servicio' | 'red' | 'desconocido';

export interface ErrorLegible {
  tipo: TipoError;
  titulo: string;
  mensaje: string;
  errores: { registro?: number; id?: string | null; campo?: string | null; motivo: string }[];
  ayuda?: string;
}

export const describirError = (error: unknown): ErrorLegible => {
  if (!axios.isAxiosError(error)) {
    return { tipo: 'desconocido', titulo: 'Error inesperado', mensaje: 'Ocurrió un error en la interfaz.', errores: [] };
  }
  if (!error.response) {
    return {
      tipo: 'red', titulo: 'Sin conexión con la API',
      mensaje: 'No se pudo contactar con el servidor. Revisa tu conexión e inténtalo de nuevo; el resto del panel puede seguir funcionando.',
      errores: [],
    };
  }
  const estado = error.response.status;
  const detalle = (error.response.data as { detail?: unknown } | undefined)?.detail;
  const estructurado = detalle && typeof detalle === 'object' ? detalle as {
    mensaje?: string; errores?: ErrorLegible['errores']; ayuda?: string;
  } : null;
  const mensaje = estructurado?.mensaje ?? (typeof detalle === 'string' ? detalle : '');
  const base = { errores: estructurado?.errores ?? [], ayuda: estructurado?.ayuda };
  if (estado === 413) {
    return { ...base, tipo: 'tamano', titulo: 'Archivo demasiado grande', mensaje: 'El máximo es 5 MiB por archivo. Divide el lote en archivos más pequeños.' };
  }
  if (estado === 409) {
    return { ...base, tipo: 'conflicto', titulo: 'Conflicto con datos existentes', mensaje: mensaje || 'El lote entra en conflicto con datos ya registrados.' };
  }
  if (estado === 400) {
    return { ...base, tipo: 'formato', titulo: 'Formato no soportado', mensaje: mensaje || 'Usa JSON, JSONL o CSV.' };
  }
  if (estado === 422) {
    return { ...base, tipo: 'validacion', titulo: 'El archivo no pasó la validación', mensaje: mensaje || 'Revisa los campos del archivo.' };
  }
  if (estado >= 500) {
    return { ...base, tipo: 'servicio', titulo: 'Servicio no disponible', mensaje: mensaje || 'El servidor no pudo completar la operación. Inténtalo de nuevo en unos minutos.' };
  }
  return { ...base, tipo: 'desconocido', titulo: `Error ${estado}`, mensaje: mensaje || 'La API rechazó la solicitud.' };
};
