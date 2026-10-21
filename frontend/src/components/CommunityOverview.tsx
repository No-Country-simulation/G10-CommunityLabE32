'use client';

import UiTree from '@/components/UiTree';
import Link from 'next/link';
import { useState } from 'react';
import { Search, UploadCloud, MessageSquare, FileText, BarChart3, ArrowUpRight, Bell, Activity, LayoutGrid, List } from 'lucide-react';
import type { DashboardKPIs } from '@/services/api';
const modulos=[
  {href:'/ingesta',nombre:'Ingesta de lotes',detalle:'Importación de mensajes',nota:'JSON · JSONL · CSV · Discord',icon:UploadCloud},
  {href:'/curaduria',nombre:'Borradores',detalle:'Contenido generado por IA',nota:'Revisión y aprobación editorial',icon:FileText},
  {href:'/interacciones',nombre:'Interacciones',detalle:'Las conversaciones de tu comunidad',nota:'Fuentes originales y contexto',icon:MessageSquare},
  {href:'/analitica',nombre:'Analítica',detalle:'Inteligencia comunitaria',nota:'Sentimiento · temas · indicadores',icon:BarChart3},
];
export default function CommunityOverview({kpis}:{kpis:DashboardKPIs|null}) {
  const [busqueda,setBusqueda]=useState('');
  const [lista,setLista]=useState(false);
  const filtrados=modulos.filter(m=>(m.nombre+' '+m.detalle).toLowerCase().includes(busqueda.toLowerCase()));
  return <UiTree>{<section className="workspace-overview" aria-label="Resumen del espacio de trabajo">
    <div className="workspace-toolbar"><label className="workspace-module-search"><Search size={15}/><input aria-label="Buscar módulos" placeholder="Buscar en tu comunidad…" value={busqueda} onChange={e=>setBusqueda(e.target.value)}/></label><div className="workspace-view-toggle" role="group" aria-label="Vista de módulos"><button aria-label="Vista de tarjetas" aria-pressed={!lista} onClick={()=>setLista(false)}><LayoutGrid size={16}/></button><button aria-label="Vista de lista" aria-pressed={lista} onClick={()=>setLista(true)}><List size={16}/></button></div></div>
    <div className="workspace-overview-grid"><div className="workspace-summary-column"><h2>Actividad</h2><div className="workspace-panel"><div className="workspace-panel-title"><strong>Resumen de la comunidad</strong><span>Global</span></div>{[{nombre:'Mensajes recibidos',valor:kpis?.total_mensajes},{nombre:'Contenidos generados',valor:kpis?.activos_generados},{nombre:'Pendientes de revisión',valor:kpis?.borradores_pendientes},{nombre:'Contenidos aprobados',valor:kpis?.activos_aprobados}].map(m=><div className="workspace-usage-row" key={m.nombre}><span><span className="workspace-status-ring"/>{m.nombre}</span><strong>{m.valor?.toLocaleString('es')??'—'}</strong></div>)}</div><h2>Alertas internas</h2><div className="workspace-panel workspace-empty-panel"><Bell size={21}/><p>{kpis?`${kpis.alertas_internas} alertas internas en tu comunidad.`:'Conecta el backend para consultar las señales de tu comunidad.'}</p><Link href="/interacciones">Ver interacciones <ArrowUpRight size={13}/></Link></div><h2>Tu flujo de trabajo</h2><div className="workspace-panel workspace-empty-panel"><Activity size={21}/><p>Importa conversaciones, analiza señales y revisa el contenido generado con IA.</p><Link href="/ingesta">Comenzar con una ingesta <ArrowUpRight size={13}/></Link></div></div>
    <div className="workspace-modules-column"><h2>Módulos</h2><div className={lista?'workspace-module-list':'workspace-module-grid'}>{filtrados.map(({href,nombre,detalle,nota,icon:Icon})=><Link className="workspace-module-card" key={href} href={href}><div className="workspace-module-card-top"><span className="workspace-module-icon"><Icon size={18}/></span><div><h3>{nombre}</h3><p>{detalle}</p></div><ArrowUpRight size={14}/></div><div className="workspace-module-note"><span className="workspace-status-ring"/>{nota}</div></Link>)}</div>{filtrados.length===0&&<p className="workspace-no-results">No hay módulos que coincidan con tu búsqueda.</p>}<div className="workspace-community-note"><span className="workspace-status-ring"/><span>Community Radar</span><span>G10 · CommunityLab E32</span></div></div></div>
  </section>}</UiTree>;
}
