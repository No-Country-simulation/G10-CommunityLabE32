'use client';

import { useSyncExternalStore } from 'react';
import { obtenerIdioma, suscribirIdioma, type Language } from '@/i18n/idioma';
import { translateText } from '@/i18n/translate';

// Idioma elegido en Configuraciones (español por defecto). En el servidor siempre es español,
// así que el primer render coincide y el cambio se aplica al hidratar.
// t(es, en): el portugués se toma del diccionario usando el texto en español como clave.
export default function useAuthLanguage(): { language: Language; t: (es: string, en: string) => string } {
  const language = useSyncExternalStore(suscribirIdioma, obtenerIdioma, () => 'es' as Language);
  return { language, t: (es: string, en: string) => language === 'en' ? en : language === 'pt' ? translateText(es, 'pt') : es };
}
