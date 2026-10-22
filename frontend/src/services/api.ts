import axios from 'axios';
import { borradoresReferencia } from './borradoresReferencia';
import { esReferenciaPublicada, kpisReferencia, resumenReferencia, mensajesReferencia } from './referenciaPublicada';

// Configuración base apuntando a tu FastAPI a través del proxy (/api)
export const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// --- Sesión: cookie HttpOnly + CSRF (ver docs/politica-acceso.md) ---
// El JWT viaja solo en la cookie HttpOnly `cl_sesion` (mismo origen, el navegador la envía sola):
// JavaScript no puede leerla. El token CSRF se guarda SOLO en memoria y se recupera con
// GET /auth/sesion tras recargar. No se guarda ningún token en localStorage ni sessionStorage.
export const EVENTO_SESION = 'communitylab-sesion';
const METODOS_SEGUROS = ['get', 'head', 'options'];
// Claves que versiones anteriores usaban para guardar tokens: se eliminan del navegador.
const CLAVES_ANTIGUAS = ['access_token', 'communitylab_token', 'token', 'token_jwt', 'communitylab-usuario'];

export type RolUsuario = 'usuario' | 'operador' | 'administrador';

export interface UsuarioAuth {
  id: number;
  email: string;
  full_name?: string | null;
  rol: RolUsuario;
  is_active: boolean;
}

interface RespuestaSesion {
  usuario: UsuarioAuth;
  csrf_token: string;
  expira: string;
}

let csrfToken = '';
let usuarioActual: UsuarioAuth | null = null;
let sesionEnCurso: Promise<UsuarioAuth | null> | null = null;

const limpiarAlmacenamientoAntiguo = () => {
  if (typeof window === 'undefined') return;
  try {
    CLAVES_ANTIGUAS.forEach((clave) => localStorage.removeItem(clave));
    ['access_token', 'communitylab-operador'].forEach((clave) => sessionStorage.removeItem(clave));
  } catch {}
};
limpiarAlmacenamientoAntiguo();

const fijarSesion = (datos: RespuestaSesion | null) => {
  csrfToken = datos?.csrf_token ?? '';
  usuarioActual = datos?.usuario ?? null;
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(EVENTO_SESION));
};

export const usuarioEnMemoria = (): UsuarioAuth | null => usuarioActual;

export const esOperador = (usuario: UsuarioAuth | null): boolean =>
  usuario?.rol === 'operador' || usuario?.rol === 'administrador';

// Única cabecera añadida: X-CSRF-Token en peticiones que modifican estado.
apiClient.interceptors.request.use((config) => {
  if (csrfToken && !METODOS_SEGUROS.includes((config.method || 'get').toLowerCase())) {
    config.headers.set('X-CSRF-Token', csrfToken);
  }
  return config;
});

// Sesión vencida o revocada a mitad de uso: limpiar el estado y volver al login (sin bucles en /login).
apiClient.interceptors.response.use(
  (respuesta) => respuesta,
  (error) => {
    const url = String(error?.config?.url ?? '');
    if (
      axios.isAxiosError(error) && error.response?.status === 401 && typeof window !== 'undefined'
      && !url.startsWith('/auth/') && !['/login', '/register'].includes(window.location.pathname)
    ) {
      fijarSesion(null);
      window.location.assign('/login');
    }
    return Promise.reject(error);
  },
);

// --- Funciones de Autenticación (Login, Sesión, Registro y Cierre) ---
export const iniciarSesion = async (email: string, password: string): Promise<UsuarioAuth> => {
  const formData = new URLSearchParams();
  formData.append('username', email);
  formData.append('password', password);

  const response = await apiClient.post<RespuestaSesion>('/auth/login', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  fijarSesion(response.data);
  return response.data.usuario;
};

/** Sesión vigente según el servidor (null si no hay o expiró). Una sola petición a la vez. */
export const obtenerSesion = async (): Promise<UsuarioAuth | null> => {
  if (!sesionEnCurso) {
    sesionEnCurso = apiClient
      .get<RespuestaSesion>('/auth/sesion')
      .then((r) => {
        fijarSesion(r.data);
        return r.data.usuario;
      })
      .catch((error) => {
        if (axios.isAxiosError(error) && error.response?.status === 401) {
          fijarSesion(null);
          return null;
        }
        throw error;
      })
      .finally(() => {
        sesionEnCurso = null;
      });
  }
  return sesionEnCurso;
};

/** Revoca la sesión en el servidor y borra el estado local aunque la petición falle. */
export const cerrarSesion = async (): Promise<void> => {
  try {
    await apiClient.post('/auth/logout');
  } catch {
    // Sin conexión o sesión ya vencida: igual se limpia el estado local.
  } finally {
    fijarSesion(null);
  }
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
  alerta_interna?: boolean;
  estado_borrador?: 'aprobado' | 'pendiente' | 'rechazado' | null;
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

export const obtenerResumenSentimiento = async (canal?: string, ambito?: Ambito | Ambito[] | null): Promise<ResumenSentimiento> => {
  if (esReferenciaPublicada() && !canal && !ambito) return structuredClone(resumenReferencia);
  const response = await apiClient.get('/mensajes/sentimiento/resumen', {
    params: { canal, ...parametrosLotes(ambito) },
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
  ambito?: Ambito | Ambito[] | null,
  sentimiento?: FiltroSentimiento,
  busqueda?: string,
): Promise<PaginatedMensajes> => {
  if (esReferenciaPublicada() && !ambito) {
    const muestra = mensajesReferencia.filter(m => (!canal || m.canal === canal) && (!sentimiento || (sentimiento === 'sin_analizar' ? !m.sentimiento_ref : m.sentimiento_ref === sentimiento)));
    const q = busqueda?.trim().toLocaleLowerCase('es');
    const encontrados = q ? muestra.filter(m => [m.texto, m.autor, m.canal].some(v => v?.toLocaleLowerCase('es').includes(q))) : muestra;
    return { items: structuredClone(encontrados.slice(skip, skip + limit)), total: encontrados.length };
  }
  const response = await apiClient.get('/mensajes', {
    params: { skip, limit, canal, ...parametrosLotes(ambito), sentimiento, q: busqueda?.trim() || undefined },
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
export type FormatoActivo = 'linkedin' | 'x' | 'faq' | 'newsletter';

export interface FuenteMensajeDetalle {
  id_mensaje: string;
  autor: string;
  canal: string;
  fecha: string;
  texto: string;
}

export interface Activo {
  historial?: { estado: EstadoActivo; fecha: string; comentario?: string }[];
  posts_redes?: { linkedin: string; x: string };
  elegibilidad_curaduria?: { sentimiento: string; logro_completado: boolean; tipo_logro: string };
  id_activo: string;
  formato: FormatoActivo;
  titulo: string;
  copy: string;
  estado: EstadoActivo;
  fuentes: string[];
  version: number;
  comentario_curador?: string;
  advertencias_fidelidad?: AdvertenciaFidelidad[] | null;
  /** Copia de la versión aprobada en OCI Object Storage; null o ausente si nunca se aprobó. */
  almacenamiento_oci?: AlmacenamientoOCI | null;
  fecha_actualizacion: string;
  fuentes_detalle?: FuenteMensajeDetalle[];
}

export interface AlmacenamientoOCI {
  estado: 'guardado' | 'error' | 'desactivado';
  fecha?: string;
  bucket?: string;
  objetos?: string[];
  error?: string;
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
  trabajo?: string | null,
  estados?: string,
): Promise<PaginatedActivosResponse> => {
  if (esReferenciaPublicada() && !trabajo) {
    const muestra = borradoresReferencia.filter(a => (!estado || a.estado === estado) && (!estados || estados.split(',').includes(a.estado)));
    return { items: structuredClone(muestra.slice((page - 1) * limit, page * limit)), total: muestra.length, page, limit, total_pages: Math.max(1, Math.ceil(muestra.length / limit)) };
  }
  const params: Record<string, string | number> = { page, limit };
  if (estado) params.estado = estado;
  if (estados) params.estados = estados;
  if (trabajo) params.trabajo = trabajo;

  const response = await apiClient.get('/curaduria/activos', { params });
  return response.data;
};

export const obtenerDetalleActivo = async (id_activo: string): Promise<Activo> => {
  if (esReferenciaPublicada() && id_activo.startsWith('referencia-')) {
    const muestra = borradoresReferencia.find(a => a.id_activo === id_activo);
    if (!muestra) throw new Error('Borrador de referencia no disponible.');
    return structuredClone(muestra);
  }
  const response = await apiClient.get(`/curaduria/activos/${id_activo}`);
  return response.data;
};

export const actualizarActivo = async (
  id_activo: string,
  payload: { copy?: string; estado?: string; comentario_curador?: string; posts_redes?: { linkedin: string; x: string } }
): Promise<Activo> => {
  if (id_activo.startsWith('referencia-')) throw new Error('Esta muestra es de solo lectura; no modifica el sitio publicado.');
  const response = await apiClient.patch(`/curaduria/activos/${id_activo}`, payload);
  return response.data;
};

// Semántica documentada en docs/metricas-panel.md.
export interface DashboardKPIs {
  recurrencia?: {
    preguntas: { texto: string; cantidad: number }[];
    palabras: { texto: string; cantidad: number }[];
  };
  /** Número de mensajes sin responder; lo proporciona el backend cuando esté disponible. */
  mensajes_sin_responder?: number;
  total_mensajes: number;
  mensajes_por_tipo: Record<string, number>;
  /** Temas que la IA asignó a los mensajes del ámbito, del más frecuente al menos (máximo 10). */
  temas_principales?: { tema: string; cantidad: number }[];
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
  fuente_ingesta?: 'discord' | 'manual' | null;
  origen: string;
  periodo: string;
  trabajos?: number;
  terminados?: number;
  ultimo?: string | null;
}

function parametrosLotes(ambito?: Ambito | Ambito[] | null): { lotes?: string } {
  // null/undefined: global. []: sin lotes. Una selección siempre usa el contrato JSON.
  if (ambito == null) return {};
  const lotes = (Array.isArray(ambito) ? ambito : [ambito]).map(({ origen, periodo, fuente_ingesta }) => ({ origen, periodo, fuente_ingesta: fuente_ingesta || null }));
  const unicos = [...new Map(lotes.map(lote => [JSON.stringify(lote), lote])).values()];
  return { lotes: JSON.stringify(unicos) };
}

// Campana: mensajes con alerta interna real del análisis (frustración, bloqueo, etc.). El backend no
// registra respuestas en Discord, así que no existe un conteo de «sin responder».
export const obtenerAlertasInternas = async (): Promise<number> => {
  const response = await apiClient.get<DashboardKPIs>('/dashboard/kpis', { timeout: 10000 });
  return response.data.alertas_internas;
};

export const obtenerKPIs = async (ambito?: Ambito | Ambito[] | null): Promise<DashboardKPIs> => {
  if (esReferenciaPublicada() && !ambito) return structuredClone(kpisReferencia);
  const response = await apiClient.get('/dashboard/kpis', {
    params: parametrosLotes(ambito),
  });
  return response.data;
};

export const obtenerAmbitos = async (): Promise<Ambito[]> => {
  if (esReferenciaPublicada()) return [];
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
  const codigo = (detalle as { codigo?: string } | undefined)?.codigo;
  if (estado === 401 || (estado === 503 && (codigo === 'acceso_no_configurado' || codigo === 'autenticacion_no_configurada'))) {
    return {
      ...base, tipo: 'acceso', titulo: 'Sesión requerida',
      mensaje: estado === 401
        ? (mensaje || 'Tu sesión expiró o no has iniciado sesión. Ingresa con tu cuenta para continuar.')
        : codigo === 'autenticacion_no_configurada'
          ? 'El inicio de sesión no está configurado en el servidor todavía. Avisa al administrador.'
          : 'El servidor no tiene configurado el acceso de operador; la acción está deshabilitada.',
    };
  }
  if (estado === 403) {
    return {
      ...base, tipo: 'acceso', titulo: codigo === 'csrf_invalido' ? 'Sesión desactualizada' : 'Sin permiso',
      mensaje: codigo === 'csrf_invalido'
        ? 'Recarga la página para renovar la sesión e inténtalo de nuevo.'
        : (mensaje || 'Tu cuenta no tiene permiso para esta acción. Pide a un administrador el rol de operador.'),
    };
  }
  if (estado === 429) {
    return { ...base, tipo: 'acceso', titulo: 'Demasiados intentos', mensaje: mensaje || 'Espera unos minutos e inténtalo de nuevo.' };
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
// --- Importación histórica de Discord por canal y fechas (PR #36) ---
export interface VerificacionCanalDiscord {
  canal: { id: string; nombre: string; tipo: number; tipo_nombre: string };
  servidor: { id: string; nombre: string };
  autorizado_en_herramienta: boolean;
  bot_en_servidor: boolean;
  permisos: { ver_canal: boolean; leer_historial: boolean };
  tipo_soportado: boolean;
}

export interface PrevisualizacionDiscord extends VerificacionCanalDiscord {
  rango: {
    inicio_utc: string;
    fin_utc_exclusivo: string;
    zona: string;
    inicio_local: string;
    fin_local_exclusivo: string;
    dias: number;
  };
  alcance_congelado: { desde: string; hasta: string; zona: string };
  limites: {
    max_mensajes: number;
    max_mensajes_configurado: number;
    max_dias: number;
    requiere_confirmacion: boolean;
    umbral_confirmacion: { dias: number; mensajes: number };
  };
  conteo:
    | { tipo: 'exacto'; mensajes_en_rango: number; importables: number }
    | { tipo: 'desconocido'; minimo: number; estimacion_aproximada: number | null; nota: string };
  alcance: string;
  advertencias: string[];
  llamadas_discord: number;
  muestra?: { id_mensaje: string; fecha: string; autor_id: string; texto: string }[];
}

export type EstadoImportacionDiscord =
  | 'pendiente'
  | 'ejecutando'
  | 'completada'
  | 'completada_con_limite'
  | 'cancelada'
  | 'error';

export interface ImportacionDiscord {
  id: string;
  guild_id?: string;
  canal_id: string;
  canal_nombre?: string | null;
  canal_tipo?: number | null;
  desde_utc?: string;
  hasta_utc?: string;
  zona: string;
  desde_local: string;
  hasta_local: string;
  max_mensajes: number;
  solicitante?: string;
  estado: EstadoImportacionDiscord;
  cancelacion_solicitada?: boolean;
  paginas: number;
  examinados: number;
  en_rango: number;
  insertados: number;
  existentes: number;
  existentes_en_vivo: number;
  editados: number;
  descartados?: Record<string, number>;
  hilos_detectados: number;
  limite_alcanzado: boolean;
  motivos_parcial?: string[];
  error?: { codigo: string; reanudable?: boolean; detalle?: string } | null;
  creado: string;
  iniciado?: string | null;
  finalizado?: string | null;
}

export interface MensajeHistoricoDiscord {
  id_mensaje: string;
  message_id: string;
  autor_id: string;
  fecha: string;
  texto: string;
  contenido_disponible: boolean;
  resultado?: string;
  estado_ia?: 'sin_evidencia' | 'pendiente' | 'fallido' | 'procesado';
}

export const verificarCanalDiscord = async (canal_id: string): Promise<VerificacionCanalDiscord> => {
  const response = await apiClient.post('/v1/discord/historico/verificar', { canal_id: canal_id.trim() });
  return response.data;
};

export const previsualizarDiscordHistorico = async (payload: {
  canal_id: string;
  desde: string;
  hasta: string;
  zona: string;
  max_mensajes?: number;
  incluir_muestra?: boolean;
}): Promise<PrevisualizacionDiscord> => {
  const response = await apiClient.post('/v1/discord/historico/previsualizar', payload);
  return response.data;
};

export const crearImportacionDiscord = async (
  payload: {
    canal_id: string;
    desde: string;
    hasta: string;
    zona: string;
    max_mensajes?: number;
    confirmar_alcance?: boolean;
  },
  idempotencyKey?: string
): Promise<{ importacion: ImportacionDiscord; reutilizada: boolean; advertencias: string[] }> => {
  const headers = idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined;
  const response = await apiClient.post('/v1/discord/historico/importaciones', payload, { headers });
  return response.data;
};

export const listarImportacionesDiscord = async (limite: number = 10): Promise<{ items: ImportacionDiscord[] }> => {
  const response = await apiClient.get('/v1/discord/historico/importaciones', { params: { limite } });
  return response.data;
};

export const consultarImportacionDiscord = async (id: string): Promise<ImportacionDiscord> => {
  const response = await apiClient.get(`/v1/discord/historico/importaciones/${encodeURIComponent(id)}`);
  return response.data;
};

export const cancelarImportacionDiscord = async (id: string): Promise<ImportacionDiscord> => {
  const response = await apiClient.post(`/v1/discord/historico/importaciones/${encodeURIComponent(id)}/cancelar`);
  return response.data;
};

export const reanudarImportacionDiscord = async (id: string): Promise<ImportacionDiscord> => {
  const response = await apiClient.post(`/v1/discord/historico/importaciones/${encodeURIComponent(id)}/reanudar`);
  return response.data;
};

export const obtenerMensajesImportacionDiscord = async (
  id: string,
  limite: number = 50,
  desplazamiento: number = 0
): Promise<{ total: number; items: MensajeHistoricoDiscord[] }> => {
  const response = await apiClient.get(
    `/v1/discord/historico/importaciones/${encodeURIComponent(id)}/mensajes`,
    { params: { limite, desplazamiento } }
  );
  return response.data;
};

export interface EstadoDiscordHistorico {
  estado: 'disponible' | 'sin_configurar' | 'configuracion_invalida';
  configurado: boolean;
  servidores: number;
  canales: number;
}

export const obtenerEstadoDiscordHistorico = async (): Promise<EstadoDiscordHistorico> => {
  const response = await apiClient.get('/v1/discord/historico/estado');
  return response.data;
};

export const ESTADOS_FINALES_DISCORD: EstadoImportacionDiscord[] = ['completada', 'completada_con_limite', 'cancelada', 'error'];

export interface ResumenAnalisisDiscord {
  total: number;
  ya_en_analisis: number;
  sin_contenido: number;
  pendientes: number;
  lotes: number;
  semanas: string[];
  origen: string;
  importacion_finalizada: boolean;
  trabajos?: { procesamiento_id: string; periodo: string; mensajes: number; reutilizado: boolean }[];
}

export const obtenerResumenAnalisisDiscord = async (id: string): Promise<ResumenAnalisisDiscord> => {
  const response = await apiClient.get(`/v1/discord/historico/importaciones/${encodeURIComponent(id)}/analisis`);
  return response.data;
};

export const enviarImportacionAAnalisis = async (id: string): Promise<ResumenAnalisisDiscord> => {
  const response = await apiClient.post(`/v1/discord/historico/importaciones/${encodeURIComponent(id)}/analisis`);
  return response.data;
};

// --- Administración de cuentas (solo rol administrador) ---
export interface UsuarioAdmin extends UsuarioAuth {
  created_at: string;
}

export const listarUsuarios = async (): Promise<UsuarioAdmin[]> => {
  const response = await apiClient.get('/auth/usuarios');
  return response.data;
};

export const crearUsuarioAdmin = async (datos: {
  email: string;
  full_name?: string;
  password: string;
  rol: RolUsuario;
}): Promise<UsuarioAdmin> => {
  const response = await apiClient.post('/auth/usuarios', datos);
  return response.data;
};

export const actualizarUsuarioAdmin = async (
  id: number,
  datos: { rol?: RolUsuario; is_active?: boolean; new_password?: string },
): Promise<UsuarioAdmin> => {
  const response = await apiClient.patch(`/auth/usuarios/${id}`, datos);
  return response.data;
};

export default apiClient;// Contrato preparado para verificación con Claude Code; requiere soporte del backend.
export interface EstadoEscuchaDiscord { canal_id: string; conectado: boolean; escuchando: boolean }
function validarEstadoEscucha(datos: EstadoEscuchaDiscord, canalId: string) {
  if (datos.canal_id !== canalId || typeof datos.conectado !== 'boolean' || typeof datos.escuchando !== 'boolean') throw new Error('Respuesta de estado de Discord no válida.');
  return datos;
}
export async function obtenerEscuchaDiscord(canalId: string, signal?: AbortSignal): Promise<EstadoEscuchaDiscord> {
  const response = await apiClient.get('/v1/discord/canales/' + encodeURIComponent(canalId) + '/escucha', { signal, timeout: 10000 });
  return validarEstadoEscucha(response.data, canalId);
}
export async function cambiarEscuchaDiscord(canalId: string, escuchando: boolean): Promise<EstadoEscuchaDiscord> {
  const response = await apiClient.patch('/v1/discord/canales/' + encodeURIComponent(canalId) + '/escucha', { escuchando }, { timeout: 10000 });
  return validarEstadoEscucha(response.data, canalId);
}

export function esLogroAcademicoElegible(activo: Activo): boolean {
  const validacion = activo.elegibilidad_curaduria;
  // Sin el dato (el backend actual aún no lo envía) no se descarta: se activa la regla estricta cuando exista.
  if (validacion === undefined) return true;
  return validacion?.sentimiento === 'positivo' && validacion.logro_completado === true && ['curso', 'diplomado', 'certificacion'].includes(validacion.tipo_logro);
}
export async function listarLogrosCuraduria(page = 1, limit = 10, estado?: string, trabajo?: string | null): Promise<PaginatedActivosResponse> {
  if (esReferenciaPublicada() && !trabajo) {
    const items = borradoresReferencia.filter(a => esLogroAcademicoElegible(a) && (!estado || (estado === 'pendientes' ? ['generado', 'revisado'].includes(a.estado) : a.estado === estado)));
    return { items: structuredClone(items.slice((page - 1) * limit, page * limit)), total: items.length, page, limit, total_pages: Math.max(1, Math.ceil(items.length / limit)) };
  }
  // Pendientes = generado + revisado en una sola consulta paginada en el servidor (`estados`). El backend aún
  // ignora `tipo_revision`, `sentimiento` y `logro_completado`; el filtro de logro académico solo se aplica
  // cuando el servidor envía `elegibilidad_curaduria` (ver esLogroAcademicoElegible).
  const response = await apiClient.get<PaginatedActivosResponse>('/curaduria/activos', { params: {
    page, limit, trabajo: trabajo || undefined, tipo_revision: 'logro_academico', sentimiento: 'positivo', logro_completado: true,
    ...(estado === 'pendientes' ? { estados: 'generado,revisado' } : { estado }),
  } });
  return { ...response.data, items: response.data.items.filter(esLogroAcademicoElegible) };
}
export async function generarPostsLogro(idActivo: string): Promise<{ linkedin: string; x: string }> {
  if (idActivo.startsWith('referencia-')) throw new Error('La muestra local no admite generación real.');
  const response = await apiClient.post('/curaduria/activos/' + encodeURIComponent(idActivo) + '/posts/generar', { redes: ['linkedin', 'x'] });
  if (typeof response.data.linkedin !== 'string' || typeof response.data.x !== 'string') throw new Error('El servidor no devolvió ambos textos de publicación.');
  return { linkedin: response.data.linkedin, x: response.data.x };
}


// Comparte el mismo conjunto y total filtrado que la pestaña Pendientes.
export async function obtenerPendientesCuraduria(): Promise<number> {
  const resultado = await listarLogrosCuraduria(1, 1, 'pendientes');
  if (!Number.isSafeInteger(resultado.total) || resultado.total < 0) throw new Error('Conteo de pendientes no disponible.');
  return resultado.total;
}

// Contrato de alertas internas del Resumen, con paginación por desplazamiento.
export interface AlertaInterna {
  id_alerta: string;
  id_mensaje: string;
  motivo: string;
  nivel: string;
  autor: string;
  canal: string;
  fecha: string | null;
  texto: string;
  origen: string | null;
  periodo: string | null;
  trabajo: string | null;
  detectada: string | null;
  veces: number;
  sentimiento_ref: string | null;
}
export async function listarAlertasInternas(skip = 0, limit = 9, ambito?: Ambito | Ambito[] | null): Promise<{ items: AlertaInterna[]; total: number }> {
  const response = await apiClient.get('/dashboard/alertas', { params: { skip, limit, ...parametrosLotes(ambito) } });
  return response.data;
}

// --- Datos cargados (Ingesta; solo administradores; la API vuelve a exigir el rol) ---
export interface LoteCargado {
  origen: string;
  periodo: string;
  fuente_ingesta: 'discord' | 'manual';
  oculto: boolean;
  trabajos: number;
  en_proceso: number;
  mensajes: number;
  /** Mensajes que otro lote también usa: se conservan si se elimina este lote. */
  mensajes_compartidos: number;
  activos: number;
  aprobados: number;
  primero: string | null;
  ultimo: string | null;
}
export type LoteClave = Pick<LoteCargado, 'origen' | 'periodo' | 'fuente_ingesta'>;
export interface PlanEliminacion {
  lotes: number; trabajos: number; en_proceso: number; mensajes: number; mensajes_conservados: number;
  activos: number; aprobados: number; banners: number;
}
const claveLote = ({ origen, periodo, fuente_ingesta }: LoteClave): LoteClave => ({ origen, periodo, fuente_ingesta });
export async function listarLotesCargados(): Promise<LoteCargado[]> {
  return (await apiClient.get('/v1/datos/lotes')).data.items;
}
export async function cambiarVisibilidadLotes(lotes: LoteClave[], oculto: boolean): Promise<number> {
  return (await apiClient.patch('/v1/datos/lotes/visibilidad', { lotes: lotes.map(claveLote), oculto })).data.trabajos_actualizados;
}
export async function previsualizarEliminacion(lotes: LoteClave[]): Promise<PlanEliminacion> {
  return (await apiClient.post('/v1/datos/lotes/eliminacion/vista-previa', { lotes: lotes.map(claveLote) })).data;
}
export async function eliminarLotes(lotes: LoteClave[], incluirAprobados: boolean): Promise<PlanEliminacion> {
  return (await apiClient.post('/v1/datos/lotes/eliminacion', {
    lotes: lotes.map(claveLote), confirmacion: 'ELIMINAR', incluir_aprobados: incluirAprobados,
  })).data;
}
