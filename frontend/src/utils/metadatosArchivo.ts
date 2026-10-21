type Registro = Record<string, unknown>;
function objeto(value: unknown): Registro { return value && typeof value === 'object' && !Array.isArray(value) ? value as Registro : {}; }
function texto(registro: Registro, claves: string[]): string { for (const clave of claves) { const value = registro[clave]; if (typeof value === 'string' && value.trim()) return value.trim(); } return ''; }
function leerCsv(texto: string): Registro[] {
  const filas: string[][] = []; let fila: string[] = [], campo = '', comillas = false;
  for (let i = 0; i < texto.length; i++) {
    const c = texto[i];
    if (c === '"') { if (comillas && texto[i + 1] === '"') { campo += '"'; i++; } else comillas = !comillas; }
    else if (c === ',' && !comillas) { fila.push(campo); campo = ''; }
    else if ((c === '\n' || c === '\r') && !comillas) { if (c === '\r' && texto[i + 1] === '\n') i++; fila.push(campo); if (fila.some(v => v.trim())) filas.push(fila); fila = []; campo = ''; }
    else campo += c;
  }
  if (comillas) throw new Error('El archivo CSV contiene comillas sin cerrar.');
  fila.push(campo); if (fila.some(v => v.trim())) filas.push(fila);
  const cabecera = filas.shift()?.map(c => c.trim()) ?? [];
  return filas.map(f => Object.fromEntries(cabecera.map((c, i) => [c, f[i] ?? ''])));
}
export function detectarMetadatosArchivo(nombreArchivo: string, contenido: string): { nombre: string; periodo: string } {
  const limpio = contenido.replace(/^\uFEFF/, '');
  let raiz: Registro = {}, registros: Registro[];
  if (nombreArchivo.toLowerCase().endsWith('.csv')) registros = leerCsv(limpio);
  else if (nombreArchivo.toLowerCase().endsWith('.jsonl')) registros = limpio.split(/\r?\n/).filter(l => l.trim()).map(l => objeto(JSON.parse(l)));
  else { const dato: unknown = JSON.parse(limpio); raiz = objeto(dato); registros = (Array.isArray(dato) ? dato : Array.isArray(raiz.interacciones) ? raiz.interacciones : []).map(objeto); }
  const metadata = { ...objeto(raiz.metadata), ...objeto(raiz.metadatos), ...raiz };
  const clavesNombre = ['nombre', 'nombre_dataset', 'origen_comunidad', 'comunidad', 'origen'];
  const nombres = [...new Set(registros.map(r => texto(r, clavesNombre)).filter(Boolean))];
  const periodos = [...new Set(registros.map(r => texto(r, ['periodo', 'período'])).filter(Boolean))];
  const nombre = texto(metadata, clavesNombre) || (nombres.length === 1 ? nombres[0] : nombreArchivo.replace(/\.(jsonl?|csv)$/i, ''));
  let periodo = texto(metadata, ['periodo', 'período']) || (periodos.length === 1 ? periodos[0] : '');
  if (!periodo && periodos.length === 0) {
    const fechas = registros.map(r => typeof r.fecha === 'string' ? r.fecha : '');
    if (fechas.length && fechas.every(f => /^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(f) && Number.isFinite(Date.parse(f)))) {
      const dias = fechas.map(f => new Date(f).toISOString().slice(0, 10)).sort();
      periodo = dias[0] === dias[dias.length - 1] ? dias[0] : dias[0] + ' / ' + dias[dias.length - 1];
    }
  }
  return { nombre, periodo };
}
