import axios from 'axios';

// Configuración base apuntando a tu FastAPI a través del proxy (/api)
export const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// --- Gestión unificada de Autenticación JWT + Compatibilidad con Operador ---
const CLAVE_OPERADOR = 'communitylab-operador';
const CLAVE_JWT = 'access_token';
const CLAVE_USUARIO = 'communitylab-usuario';
export const EVENTO_OPERADOR = 'communitylab-operador';

export interface UsuarioAuth {
  id: number;
  email: string;
  full_name?: string | null;
  is_active: boolean;
}

// --- CÓMO DEBE QUEDAR DESPUÉS ---
export const leerTokenOperador = (): string => {
  if (typeof window === 'undefined') return '';
  try {
    return (
      localStorage.getItem('access_token') ||
      localStorage.getItem('communitylab_token') ||
      localStorage.getItem('token') ||
      localStorage.getItem('token_jwt') ||
      sessionStorage.getItem('access_token') ||
      sessionStorage.getItem('communitylab-operador') ||
      ''
    );
  } catch {
    return '';
  }
};

export const guardarTokenOperador = (token: string) => {
  if (typeof window === 'undefined') return;
  try {
    if (token) {
      localStorage.setItem(CLAVE_JWT, token);
      sessionStorage.setItem(CLAVE_OPERADOR, token);
    } else {
      localStorage.removeItem(CLAVE_JWT);
      localStorage.removeItem(CLAVE_USUARIO);
      sessionStorage.removeItem(CLAVE_OPERADOR);
    }
  } catch {}
  window.dispatchEvent(new Event(EVENTO_OPERADOR));
};

export const cerrarSesion = () => {
  guardarTokenOperador('');
};

// Único interceptor limpio para inyectar el JWT en todas las peticiones
apiClient.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = leerTokenOperador();
    if (token) {
      config.headers.set('Authorization', `Bearer ${token}`);
    }
  }
  return config;
});
// --- Funciones de Autenticación (Login y Registro) ---
export interface RespuestaToken {
  access_token: string;
  token_type: string;
}

export const iniciarSesion = async (email: string, password: string): Promise<RespuestaToken> => {
  const formData = new URLSearchParams();
  formData.append('username', email);
  formData.append('password', password);

  const response = await apiClient.post<RespuestaToken>('/auth/login', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  guardarTokenOperador(response.data.access_token);
  return response.data;
};

export const registrarUsuario = async (
  full_name: string,
  email: string,
  password: string
): Promise<UsuarioAuth> => {
  const response = await apiClient.post<UsuarioAuth>('/auth/register', {
    full_name,
    email,
    password,
  });
  return response.data;
};

export const obtenerPerfilActual = async (): Promise<UsuarioAuth> => {
  const response = await apiClient.get<UsuarioAuth>('/auth/me');
  return response.data;
};
export interface ActualizarPerfilPayload {
  full_name?: string;
  email?: string;
  current_password?: string;
  new_password?: string;
}

export const actualizarPerfilUsuario = async (
  payload: ActualizarPerfilPayload
): Promise<UsuarioAuth> => {
  const response = await apiClient.patch<UsuarioAuth>('/auth/me', payload);
  return response.data;
};

// Tipado estricto basado en tu Pydantic del Backend
export interface Mensaje {
  id_mensaje: string;
  autor: string;
  fecha: string;
  canal: string;
  tipo: string;
  texto: string;
  // null = sin analizar; positivo | negativo | neutral | indeterminado.
  sentimiento_ref?: string | null;
  sentimiento_origen?: string | null;
  sentimiento_version?: string | null;
  tema_ref?: string;
}

export type Sentimiento = 'positivo' | 'negativo' | 'neutral' | 'indeterminado';
export type FiltroSentimiento = Sentimiento | 'sin_analizar';

export interface ResumenSentimiento {
  total: number;
  analizados: number;
  sin_analizar: number;
  por_valor: Record<Sentimiento, number>;
  porcentaje_sobre_analizados: Record<Sentimiento, number | null>;
  denominador: 'analizados';
  estado: 'sin_datos' | 'parcial' | 'completo';
}

export const obtenerResumenSentimiento = async (canal?: string, ambito?: Ambito | null): Promise<ResumenSentimiento> => {
  const response = await apiClient.get('/mensajes/sentimiento/resumen', {
    params: { canal, origen: ambito?.origen, periodo: ambito?.periodo },
  });
  return response.data;
};

export interface PaginatedMensajes {
  items: Mensaje[];
  total: number;
}

export const obtenerMensajes = async (
  skip: number = 0,
  limit: number = 10,
  canal?: string,
  ambito?: Ambito | null,
  sentimiento?: FiltroSentimiento,
): Promise<PaginatedMensajes> => {
  const response = await apiClient.get('/mensajes', {
    params: { skip, limit, canal, origen: ambito?.origen, periodo: ambito?.periodo, sentimiento },
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
  fuentes_detalle?: FuenteMensajeDetalle[];
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

// Semántica documentada en docs/metricas-panel.md.
export interface DashboardKPIs {
  total_mensajes: number;
  mensajes_por_tipo: Record<string, number>;
  distribucion_sentimiento: Record<Sentimiento, number>;
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
    persistencia?: { postgres: string; activos: number; sentimientos?: number };
    diagnostico?: DiagnosticoIA;
  } | null;
}

export const consultarTrabajo = async (id: string, signal?: AbortSignal): Promise<Trabajo> => {
  const response = await apiClient.get(`/v1/trabajos/${encodeURIComponent(id)}`, { signal, timeout: 15000 });
  return response.data;
};

// --- Procesar pendientes de Discord (lotes parciales sin cerrar el período) ---
export type EstadoSolicitud =
  | 'pendiente' | 'tomada' | 'en_curso' | 'sin_pendientes' | 'completada' | 'completada_con_errores' | 'cancelada';

export interface LoteSolicitud {
  periodo: string;
  nuevos: number;
  contexto: number;
  trabajo: string | null;
  estado: string;
  trabajo_estado: EstadoTrabajo | null;
  activos: number;
  alertas: number;
}

export interface SolicitudPendientes {
  id: string;
  origen: string;
  estado: EstadoSolicitud;
  lotes: LoteSolicitud[];
  mensajes_nuevos: number;
  mensajes_contexto: number;
  trabajos_terminados: number;
  trabajos_error: number;
  activos_creados: number;
  creado: string;
  actualizado: string;
  reutilizada?: boolean;
}

export interface EstadoPendientes {
  origen: string;
  solicitud: SolicitudPendientes | null;
  puente: { activo: boolean; visto: string; pendientes: number; pendientes_por_periodo: Record<string, number> | null } | null;
}

export const SOLICITUD_ABIERTA: EstadoSolicitud[] = ['pendiente', 'tomada', 'en_curso'];

export const obtenerEstadoPendientes = async (signal?: AbortSignal): Promise<EstadoPendientes> => {
  const response = await apiClient.get('/v1/procesamiento-pendientes/actual', { signal, timeout: 15000 });
  return response.data;
};

export const solicitarProcesarPendientes = async (): Promise<SolicitudPendientes> => {
  const response = await apiClient.post('/v1/procesamiento-pendientes');
  return response.data;
};

// --- Banners (solo desde un texto aprobado; aprobar el banner no lo publica) ---
export interface Banner {
  id: string;
  id_activo: string;
  version_texto: number;
  estado: 'pendiente' | 'generando' | 'generado' | 'error';
  revision: 'pendiente' | 'aprobado' | 'rechazado';
  desactualizado: boolean;
  proveedor: string;
  error_codigo: string | null;
  intentos: number;
  comentario: string | null;
  url: string | null;
  actualizado: string;
  reutilizado?: boolean;
}

export interface BannersActivo {
  id_activo: string;
  estado_activo: EstadoActivo;
  version_texto: number;
  puede_generar: boolean;
  proveedor: string;
  generacion_ia: boolean;
  banners: Banner[];
  vigente: Banner | null;
}

export const listarBanners = async (id_activo: string): Promise<BannersActivo> => {
  const response = await apiClient.get(`/curaduria/activos/${encodeURIComponent(id_activo)}/banners`);
  return response.data;
};

export const generarBanner = async (id_activo: string): Promise<Banner> => {
  const response = await apiClient.post(`/curaduria/activos/${encodeURIComponent(id_activo)}/banners`);
  return response.data;
};

export const revisarBanner = async (
  id: string, decision: 'aprobado' | 'rechazado', comentario?: string,
): Promise<Banner> => {
  const response = await apiClient.post(`/banners/${encodeURIComponent(id)}/revision`, { decision, comentario });
  return response.data;
};

// --- Errores legibles y seguros ---
export type TipoError = 'validacion' | 'tamano' | 'conflicto' | 'formato' | 'servicio' | 'red' | 'acceso' | 'desconocido';

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
  if (estado === 401 || (estado === 503 && (detalle as { codigo?: string } | undefined)?.codigo === 'acceso_no_configurado')) {
    return {
      ...base, tipo: 'acceso', titulo: 'Sesión requerida',
      mensaje: estado === 401
        ? (mensaje || 'Tu sesión expiró o no has iniciado sesión. Ingresa con tu cuenta para continuar.')
        : 'El servidor no tiene configurado el acceso de operador; la acción está deshabilitada.',
    };
  }
  if (estado === 413) {
    return { ...base, tipo: 'tamano', titulo: 'Archivo demasiado grande', mensaje: 'El máximo es 5 MiB por archivo. Divide el lote en archivos más pequeños.' };
  }
  if (estado === 409) {
    return { ...base, tipo: 'conflicto', titulo: 'Conflicto con datos existentes', mensaje: mensaje || 'El lote entra en conflicto con datos ya registrados.' };
  }
  if (estado === 400) {
    return { ...base, tipo: 'formato', titulo: 'Solicitud no válida', mensaje: mensaje || 'Revisa los datos enviados.' };
  }
  if (estado === 422) {
    return { ...base, tipo: 'validacion', titulo: 'El archivo no pasó la validación', mensaje: mensaje || 'Revisa los campos del archivo.' };
  }
  if (estado >= 500) {
    return { ...base, tipo: 'servicio', titulo: 'Servicio no disponible', mensaje: mensaje || 'El servidor no pudo completar la operación. Inténtalo de nuevo en unos minutos.' };
  }
  return { ...base, tipo: 'desconocido', titulo: `Error ${estado}`, mensaje: mensaje || 'La API rechazó la solicitud.' };
};

export default apiClient;