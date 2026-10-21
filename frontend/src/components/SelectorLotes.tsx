'use client';

import UiTree from '@/components/UiTree';
import type { Ambito } from '@/services/api';
export default function SelectorLotes({ ambitos, seleccion, setSeleccion }: { ambitos: Ambito[]; seleccion: Ambito[] | null; setSeleccion: (lotes: Ambito[] | null) => void }) {
  const claveLote = (lote: Ambito) => JSON.stringify([lote.origen, lote.periodo, lote.fuente_ingesta ?? null]);
  return <UiTree>{(              <details className="analytics-lot-picker">
                <summary>{seleccion === null ? 'Todos los lotes' : seleccion.length === 0 ? 'Selecciona lotes' : seleccion.length + (seleccion.length === 1 ? ' lote seleccionado' : ' lotes seleccionados')}</summary>
                <div className="analytics-lot-menu">
                  <label><input type="checkbox" checked={seleccion === null} onChange={(e) => setSeleccion(e.target.checked ? null : [])} />Todos los lotes</label>
                  {([
                    { fuente: 'discord', etiqueta: 'Discord' },
                    { fuente: 'manual', etiqueta: 'Carga manual · Ingesta de datos' },
                    { fuente: null, etiqueta: 'Origen sin identificar' },
                  ] as const).map((grupo) => {
                    const lotes = ambitos.filter((a) => (a.fuente_ingesta ?? null) === grupo.fuente);
                    if (grupo.fuente === null && lotes.length === 0) return null;
                    return <UiTree key={grupo.fuente ?? 'sin-origen'}>{<fieldset key={grupo.fuente ?? 'sin-origen'}><legend>{grupo.etiqueta}</legend>
                      {lotes.length === 0 ? <p>Sin lotes disponibles</p> : lotes.map((lote) => {
                        const clave = claveLote(lote);
                        return <UiTree key={clave}>{<label key={clave} translate="no"><input type="checkbox" checked={seleccion === null || seleccion.some((a) => claveLote(a) === clave)} onChange={(e) => {
                          const actuales = seleccion ?? ambitos;
                          setSeleccion(e.target.checked ? [...actuales.filter((a) => claveLote(a) !== clave), lote] : actuales.filter((a) => claveLote(a) !== clave));
                        }} />{lote.origen} · {lote.periodo}</label>}</UiTree>;
                      })}
                    </fieldset>}</UiTree>;
                  })}
                </div>
              </details>)}</UiTree>;
}
