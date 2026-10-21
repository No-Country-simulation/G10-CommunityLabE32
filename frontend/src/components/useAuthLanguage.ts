'use client';

type Language = 'es' | 'en';
// El idioma original es español; la traducción la ofrece el navegador.
export default function useAuthLanguage(): { language: Language; t: (es: string, en: string) => string } {
  return { language: 'es', t: (es: string) => es };
}
