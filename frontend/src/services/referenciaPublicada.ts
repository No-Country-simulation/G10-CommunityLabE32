import type { DashboardKPIs, Mensaje, ResumenSentimiento } from './api';
import { esVistaLocal } from './vistaLocal';

// Información visible durante la revisión autorizada de la web publicada.
// Es una captura de referencia, no una conexión a producción ni un conjunto completo.
export const esReferenciaPublicada = () => esVistaLocal()
  && process.env.NEXT_PUBLIC_REFERENCIA_PUBLICADA === 'true';
export const resumenReferencia: ResumenSentimiento = {
  total: 472, analizados: 3, sin_analizar: 469,
  por_valor: { positivo: 0, negativo: 1, neutral: 2, indeterminado: 0 },
  porcentaje_sobre_analizados: { positivo: 0, negativo: 33.3, neutral: 66.7, indeterminado: 0 },
  denominador: 'analizados', estado: 'parcial',
};
export const kpisReferencia: DashboardKPIs = {
  total_mensajes: 472,
  mensajes_por_tipo: { PREGUNTA_TECNICA: 355, CONSULTA_NEGOCIO: 68, SIN_CLASIFICAR: 48, LOGRO: 1 },
  distribucion_sentimiento: resumenReferencia.por_valor,
  sentimiento: { estado: 'parcial', clasificados: 3, sin_clasificar: 469 },
  activos_generados: 31, activos_por_estado: { generado: 28, revisado: 1, aprobado: 2, rechazado: 0 },
  borradores_pendientes: 29, activos_aprobados: 2, publicados: null,
  publicacion_externa: 'manual', alertas_internas: 5, alertas_registradas: 5,
};
const muestra = [
  ['Ana Valenzuela','comunidad','2026-10-23','Organizamos el primer hackathon interno de la comunidad: 40 participantes, 9 equipos y 3 proyectos que siguen activos. ¡Gracias a todos los mentores!'],
  ['Esteban Guzmán','oci','2026-10-23','Aprobé la certificación OCI Foundations. Usé la VM gratuita de Oracle para practicar todo lo del examen. Si alguien la va a presentar, comparto mis apuntes.'],
  ['Natalia Silva','general','2026-10-22','Jajaja qué buena reunión la de hoy 😂'],
  ['Ricardo Fuentes','logros','2026-10-22','Completé el reto de 30 días de SQL. Pasé de no saber hacer un JOIN a optimizar consultas con índices. Gracias por la paciencia en el canal 💪'],
  ['Gabriela Ortiz','soporte','2026-10-22','Estoy frustrada, ya intenté de todo y el bot no responde en el canal. Pensé en dejar el proyecto.'],
  ['Felipe Navarro','python','2026-10-22','¿Alguien sabe cómo validar un JSON de respuesta de Gemini contra un esquema para que no rompa el flujo cuando viene incompleto?'],
  ['Daniela Peña','mentorias','2026-10-21','Abro cupos para mentorías gratuitas de Python los sábados. Ya acompañé a 10 personas este mes y quiero seguir ayudando.'],
  ['Martín Salazar','cicd','2026-10-21','Logré automatizar todo el pipeline de CI/CD con GitHub Actions: pruebas, build de imágenes y despliegue en menos de 8 minutos.'],
  ['Isabela Cruz','proyectos','2026-10-21','Terminamos el dashboard de métricas de la comunidad con Next.js y FastAPI. Ya está desplegado y lo pueden probar en el canal de demos.'],
  ['Tomás Aguilar','soporte','','Necesito ayuda urgente: mañana presento y la base de datos dejó de aceptar conexiones después de actualizar la imagen de PostgreSQL.'],
];
export const mensajesReferencia: Mensaje[] = muestra.map(([autor,canal,fecha,texto], index) => ({
  id_mensaje: `referencia-${index + 1}`, autor, canal, fecha: fecha ? `${fecha}T00:00:00` : '',
  texto, tipo: '', sentimiento_ref: null,
}));
