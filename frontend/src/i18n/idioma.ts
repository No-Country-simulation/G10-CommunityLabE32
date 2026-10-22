// Idioma de la interfaz: español (original), inglés y portugués de Brasil.
// Es una preferencia de cada navegador; si el almacenamiento no está disponible, se usa español.
export type Language = 'es' | 'en' | 'pt';

export const IDIOMAS: { valor: Language; nombre: string; lang: string }[] = [
  { valor: 'es', nombre: 'Español', lang: 'es' },
  { valor: 'en', nombre: 'English', lang: 'en' },
  { valor: 'pt', nombre: 'Português (Brasil)', lang: 'pt-BR' },
];

const CLAVE = 'communitylab-idioma';
const EVENTO = 'communitylab-idioma';

function valido(valor: unknown): valor is Language {
  return valor === 'es' || valor === 'en' || valor === 'pt';
}

export function obtenerIdioma(): Language {
  if (typeof window === 'undefined') return 'es';
  try {
    const guardado = window.localStorage.getItem(CLAVE);
    return valido(guardado) ? guardado : 'es';
  } catch {
    return 'es';
  }
}

export function cambiarIdioma(idioma: Language) {
  try { window.localStorage.setItem(CLAVE, idioma); } catch { /* sin almacenamiento: solo esta pestaña */ }
  document.documentElement.lang = IDIOMAS.find(i => i.valor === idioma)?.lang ?? 'es';
  window.dispatchEvent(new Event(EVENTO));
}

export function suscribirIdioma(alCambiar: () => void) {
  window.addEventListener(EVENTO, alCambiar);
  window.addEventListener('storage', alCambiar);   // otras pestañas
  return () => { window.removeEventListener(EVENTO, alCambiar); window.removeEventListener('storage', alCambiar); };
}
