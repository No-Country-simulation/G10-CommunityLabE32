import axios from 'axios';

// Configuración base apuntando a tu FastAPI
export const apiClient = axios.create({
  baseURL: 'http://127.0.0.1:8000/api',
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
  canal?: string
): Promise<PaginatedMensajes> => {
  const response = await apiClient.get('/mensajes', { 
    params: { skip, limit, canal } 
  });
  return response.data;
};

export const subirLote = async (archivo: File) => {
  const formData = new FormData();
  formData.append('file', archivo);

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
  estado?: string
): Promise<PaginatedActivosResponse> => {
  const params: Record<string, any> = { page, limit };
  if (estado) params.estado = estado;
  
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

export interface DashboardKPIs {
  total_mensajes: number;
  distribucion_sentimiento: {
    positivo: number;
    negativo: number;
    neutral: number;
  };
  activos_generados: number;
  activos_aprobados: number;
  alertas_internas: number;
}

export const obtenerKPIs = async (): Promise<DashboardKPIs> => {
  const response = await apiClient.get('/dashboard/kpis');
  return response.data;
};