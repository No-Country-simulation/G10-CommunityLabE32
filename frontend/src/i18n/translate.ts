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
    [/^(\d+) lote\(s\) ocultos del panel\. Puedes volver a mostrarlos cuando quieras\.$/, n => n + ' batch(es) hidden from the dashboard. You can show them again at any time.'],
    [/^(\d+) lote\(s\) visibles de nuevo en el panel\.$/, n => n + ' batch(es) visible on the dashboard again.'],
    [/^Eliminados (\d+) lote\(s\): (\d+) mensaje\(s\) y (\d+) contenido\(s\)\.$/, (l, m, a) => 'Deleted ' + l + ' batch(es): ' + m + ' message(s) and ' + a + ' item(s).'],
    [/^; (\d+) se conservan porque otro lote también los usa$/, n => '; ' + n + ' are kept because another batch also uses them'],
    [/^Guardada el (.+) · (\d+) archivo\(s\)$/, (f, n) => 'Saved on ' + f + ' · ' + n + ' file(s)'],
    [/^Falló el (.+) \((.+)\)$/, (f, e) => 'Failed on ' + f + ' (' + e + ')'],
    [/^(\d+) pendientes? de Curaduría$/, n => n + ' pending in Curation'],
    [/^ID #(\d+) · Rol: (\w+)$/, (id, rol) => 'ID #' + id + ' · Role: ' + rol],
    [/^Registro (\d+)$/, n => 'Record ' + n],
    [/^ ?· (\d+) duplicadas omitidas$/, n => ' · ' + n + ' duplicates skipped'],
    [/^ ?· (\d+) de contexto ya procesado$/, n => ' · ' + n + ' already processed as context'],
    [/^Cuenta creada para (.+)\. Entrégale esta contraseña temporal por un canal privado; la cambiará en Configuraciones\.$/, e => 'Account created for ' + e + '. Share this temporary password through a private channel; they will change it in Settings.'],
    [/^Contraseña restablecida para (.+); sus sesiones abiertas se cerraron\.$/, e => 'Password reset for ' + e + '; their open sessions were signed out.'],
    [/^Cuenta (.+) actualizada; sus sesiones abiertas se cerraron\.$/, e => 'Account ' + e + ' updated; their open sessions were signed out.'],
    [/^¿Generar una contraseña temporal nueva para (.+)\?$/, e => 'Generate a new temporary password for ' + e + '?'],
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
    [/^(\d+) lote\(s\) ocultos del panel\. Puedes volver a mostrarlos cuando quieras\.$/, n => n + ' lote(s) ocultado(s) do painel. Você pode mostrá-los novamente quando quiser.'],
    [/^(\d+) lote\(s\) visibles de nuevo en el panel\.$/, n => n + ' lote(s) visível(is) novamente no painel.'],
    [/^Eliminados (\d+) lote\(s\): (\d+) mensaje\(s\) y (\d+) contenido\(s\)\.$/, (l, m, a) => l + ' lote(s) excluído(s): ' + m + ' mensagem(ns) e ' + a + ' conteúdo(s).'],
    [/^; (\d+) se conservan porque otro lote también los usa$/, n => '; ' + n + ' são mantidas porque outro lote também as usa'],
    [/^Guardada el (.+) · (\d+) archivo\(s\)$/, (f, n) => 'Salva em ' + f + ' · ' + n + ' arquivo(s)'],
    [/^Falló el (.+) \((.+)\)$/, (f, e) => 'Falhou em ' + f + ' (' + e + ')'],
    [/^(\d+) pendientes? de Curaduría$/, n => n + (n === '1' ? ' pendente' : ' pendentes') + ' de Curadoria'],
    [/^ID #(\d+) · Rol: (\w+)$/, (id, rol) => 'ID #' + id + ' · Função: ' + rol],
    [/^Registro (\d+)$/, n => 'Registro ' + n],
    [/^ ?· (\d+) duplicadas omitidas$/, n => ' · ' + n + ' duplicadas ignoradas'],
    [/^ ?· (\d+) de contexto ya procesado$/, n => ' · ' + n + ' de contexto já processado'],
    [/^Cuenta creada para (.+)\. Entrégale esta contraseña temporal por un canal privado; la cambiará en Configuraciones\.$/, e => 'Conta criada para ' + e + '. Entregue esta senha temporária por um canal privado; a pessoa vai alterá-la em Configurações.'],
    [/^Contraseña restablecida para (.+); sus sesiones abiertas se cerraron\.$/, e => 'Senha redefinida para ' + e + '; as sessões abertas foram encerradas.'],
    [/^Cuenta (.+) actualizada; sus sesiones abiertas se cerraron\.$/, e => 'Conta ' + e + ' atualizada; as sessões abertas foram encerradas.'],
    [/^¿Generar una contraseña temporal nueva para (.+)\?$/, e => 'Gerar uma nova senha temporária para ' + e + '?'],
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
