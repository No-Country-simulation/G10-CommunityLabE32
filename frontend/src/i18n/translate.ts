import dictionary from './en.json';
export type Language = 'es' | 'en';
const catalog: Record<string, string> = dictionary;
const lower = new Map(Object.entries(catalog).map(([key, value]) => [key.toLocaleLowerCase('es'), value]));
const patterns: [RegExp, (...parts: string[]) => string][] = [
  [/^(\d+) lote seleccionado$/, n => n + ' selected batch'],
  [/^(\d+) lotes seleccionados$/, n => n + ' selected batches'],
  [/^· (\d+) lote aplicado$/, n => '· ' + n + ' applied batch'],
  [/^· (\d+) lotes aplicados$/, n => '· ' + n + ' applied batches'],
  [/^(\d+) mensajes sin responder$/, n => n + ' unanswered messages'],
  [/^ID #(.*) · Sesión autenticada$/, id => 'ID #' + id + ' · Authenticated session'],
  [/^El archivo pesa (.*) MiB; el máximo es 5 MiB\.$/, size => 'The file is ' + size + ' MiB; the maximum is 5 MiB.'],
  [/^(.*) s desde el registro$/, n => n + ' s since registration'],
  [/^Análisis (.*)$/, info => 'Analysis ' + info],
  [/^Vista previa del banner, versión (.*) del texto$/, n => 'Banner preview, text version ' + n],
  [/^Este contenido tiene (.*) advertencia\(s\) de fidelidad\. ¿Confirmas que revisaste el texto frente a las fuentes\?$/, n => 'This content has ' + n + ' accuracy warning(s). Have you checked the text against the sources?'],
];
export function translateText(text: string, language: Language): string {
  if (language === 'es') return text;
  const key = text.replace(/\s+/g, ' ').trim();
  if (!key) return text;
  const translated = catalog[key] ?? lower.get(key.toLocaleLowerCase('es'));
  if (translated) return text.replace(text.trim(), translated);
  for (const [pattern, format] of patterns) { const match = key.match(pattern); if (match) return format(...match.slice(1)); }
  // Compound status/error messages contain known UI phrases separated by punctuation.
  if (key.includes('. ') || key.includes(' · ')) {
    return key.split(/(\. | · )/).map(part => part === '. ' || part === ' · ' ? part : catalog[part + '.']?.replace(/\.$/, '') ?? translateText(part, language)).join('');
  }
  return text;
}
export function translateCurrent(text: string): string {
  return text;
}
