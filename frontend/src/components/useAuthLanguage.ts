'use client';

// Authentication screens use English; translation is handled by the browser.
export default function useAuthLanguage() {
  return { language: 'en' as const, t: (_es: string, en: string) => en };
}
