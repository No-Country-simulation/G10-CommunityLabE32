// Presentación de datos de la comunidad (temas, canales e iniciales) sin cambiar lo guardado.

// Gemini guarda el tema en minúsculas para agrupar mensajes del mismo asunto; los temas
// anteriores al ajuste del prompt quedaron además sin tildes. Al mostrarlos se restituyen las
// tildes de las palabras frecuentes y se escriben las siglas en mayúsculas.
const TILDES: Record<string, string> = {
  analisis: 'análisis', api: 'API', apis: 'APIs', autenticacion: 'autenticación', aws: 'AWS',
  certificacion: 'certificación', certificaciones: 'certificaciones', ci: 'CI', cd: 'CD',
  codigo: 'código', comunicacion: 'comunicación', configuracion: 'configuración', conexion: 'conexión',
  csv: 'CSV', documentacion: 'documentación', ejecucion: 'ejecución', etl: 'ETL', gcp: 'GCP',
  http: 'HTTP', ia: 'IA', integracion: 'integración', json: 'JSON', jwt: 'JWT', logica: 'lógica',
  migracion: 'migración', migraciones: 'migraciones', modulo: 'módulo', modulos: 'módulos', oci: 'OCI',
  optimizacion: 'optimización', practica: 'práctica', practicas: 'prácticas', presentacion: 'presentación',
  programacion: 'programación', publicacion: 'publicación', sesion: 'sesión', sesiones: 'sesiones',
  sql: 'SQL', tecnica: 'técnica', tecnicas: 'técnicas', ui: 'UI', url: 'URL', ux: 'UX',
  validacion: 'validación', version: 'versión', vm: 'VM',
  // Nombres propios de herramientas frecuentes en la comunidad.
  discord: 'Discord', docker: 'Docker', fastapi: 'FastAPI', gemini: 'Gemini', github: 'GitHub',
  langgraph: 'LangGraph', linkedin: 'LinkedIn', postgresql: 'PostgreSQL', python: 'Python',
  sqlalchemy: 'SQLAlchemy',
};

export function temaLegible(tema: string): string {
  const texto = tema.trim().split(/\s+/).map(p => TILDES[p.toLocaleLowerCase('es')] ?? p).join(' ');
  return texto.charAt(0).toLocaleUpperCase('es') + texto.slice(1);
}

// Los mensajes de Discord guardan el canal como «discord_<ID numérico>», que no dice nada a quien
// lo lee. Se muestra «Discord»; el ID sigue disponible en el detalle del mensaje.
export function canalLegible(canal: string | null | undefined): string {
  const valor = (canal ?? '').trim();
  return /^discord_\d{16,22}$/.test(valor) ? 'Discord' : valor;
}

// Iniciales de nombre y apellido («Paulo Solorzano» → «PS»); con una sola palabra, sus dos primeras letras.
export function iniciales(nombre: string | null | undefined): string {
  const partes = (nombre ?? '').trim().split(/\s+/).filter(Boolean);
  if (partes.length === 0) return '?';
  const texto = partes.length === 1 ? partes[0].slice(0, 2) : partes[0][0] + partes[partes.length - 1][0];
  return texto.toLocaleUpperCase('es');
}
