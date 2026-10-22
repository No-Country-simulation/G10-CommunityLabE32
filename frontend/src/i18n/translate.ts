import en from './en.json';
import pt from './pt.json';
import { obtenerIdioma, type Language } from './idioma';

export type { Language };
type Catalogo = { exacto: Record<string, string>; minusculas: Map<string, string>; patrones: [RegExp, (...parts: string[]) => string][] };

function catalogo(diccionario: Record<string, string>, patrones: Catalogo['patrones']): Catalogo {
  return { exacto: diccionario, minusculas: new Map(Object.entries(diccionario).map(([k, v]) => [k.toLocaleLowerCase('es'), v])), patrones };
}

// El español es el original: las claves de los diccionarios son los textos en español de la interfaz.
const CATALOGOS: Record<Exclude<Language, 'es'>, Catalogo> = {
  en: catalogo(en, [
    [/^(\d+) lote seleccionado$/, n => n + ' selected batch'],
    [/^(\d+) lotes seleccionados$/, n => n + ' selected batches'],
    [/^· (\d+) lote aplicado$/, n => '· ' + n + ' applied batch'],
    [/^· (\d+) lotes aplicados$/, n => '· ' + n + ' applied batches'],
    [/^(\d+) mensajes sin responder$/, n => n + ' unanswered messages'],
    [/^(\d+) fuentes$/, n => n + ' sources'],
    [/^Sesión de (\w+) activa$/, rol => (({ administrador: 'Administrator', operador: 'Operator', usuario: 'User' } as Record<string, string>)[rol] ?? rol) + ' session active'],
    [/^ID #(.*) · Sesión autenticada$/, id => 'ID #' + id + ' · Authenticated session'],
    [/^El archivo pesa (.*) MiB; el máximo es 5 MiB\.$/, size => 'The file is ' + size + ' MiB; the maximum is 5 MiB.'],
    [/^(.*) s desde el registro$/, n => n + ' s since registration'],
    [/^Análisis (.*)$/, info => 'Analysis ' + info],
    [/^Vista previa del banner, versión (.*) del texto$/, n => 'Banner preview, text version ' + n],
    [/^Este contenido tiene (.*) advertencia\(s\) de fidelidad\. ¿Confirmas que revisaste el texto frente a las fuentes\?$/, n => 'This content has ' + n + ' accuracy warning(s). Have you checked the text against the sources?'],
  ]),
  pt: catalogo(pt, [
    [/^(\d+) lote seleccionado$/, n => n + ' lote selecionado'],
    [/^(\d+) lotes seleccionados$/, n => n + ' lotes selecionados'],
    [/^· (\d+) lote aplicado$/, n => '· ' + n + ' lote aplicado'],
    [/^· (\d+) lotes aplicados$/, n => '· ' + n + ' lotes aplicados'],
    [/^(\d+) mensajes sin responder$/, n => n + ' mensagens sem resposta'],
    [/^(\d+) fuentes$/, n => n + ' fontes'],
    [/^Sesión de (\w+) activa$/, rol => 'Sessão de ' + (({ administrador: 'administrador', operador: 'operador', usuario: 'usuário' } as Record<string, string>)[rol] ?? rol) + ' ativa'],
    [/^ID #(.*) · Sesión autenticada$/, id => 'ID #' + id + ' · Sessão autenticada'],
    [/^El archivo pesa (.*) MiB; el máximo es 5 MiB\.$/, size => 'O arquivo tem ' + size + ' MiB; o máximo é 5 MiB.'],
    [/^(.*) s desde el registro$/, n => n + ' s desde o registro'],
    [/^Análisis (.*)$/, info => 'Análise ' + info],
    [/^Vista previa del banner, versión (.*) del texto$/, n => 'Prévia do banner, versão ' + n + ' do texto'],
    [/^Este contenido tiene (.*) advertencia\(s\) de fidelidad\. ¿Confirmas que revisaste el texto frente a las fuentes\?$/, n => 'Este conteúdo tem ' + n + ' alerta(s) de fidelidade. Você confirma que revisou o texto em relação às fontes?'],
  ]),
};

export function translateText(text: string, language: Language): string {
  if (language === 'es') return text;
  const cat = CATALOGOS[language];
  const key = text.replace(/\s+/g, ' ').trim();
  if (!key) return text;
  const translated = cat.exacto[key] ?? cat.minusculas.get(key.toLocaleLowerCase('es'));
  if (translated) return text.replace(text.trim(), translated);
  for (const [pattern, format] of cat.patrones) { const match = key.match(pattern); if (match) return format(...match.slice(1)); }
  // Mensajes compuestos: frases conocidas separadas por puntuación.
  if (key.includes('. ') || key.includes(' · ')) {
    return key.split(/(\. | · )/).map(part => part === '. ' || part === ' · ' ? part : cat.exacto[part + '.']?.replace(/\.$/, '') ?? translateText(part, language)).join('');
  }
  return text;
}

// Para textos fuera del árbol de React (confirmaciones, avisos y diálogos del navegador).
export function translateCurrent(text: string): string {
  return translateText(text, obtenerIdioma());
}
