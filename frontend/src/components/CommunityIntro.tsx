import Link from 'next/link';
import { ArrowUpRight, MessageSquare, FileText, Check, ArrowRight } from 'lucide-react';
export default function CommunityIntro() {
  return <section className="gum-community-intro" aria-labelledby="community-intro-title">
    <div className="gum-intro-copy"><span className="gum-eyebrow">Equipo 32</span><h1 id="community-intro-title">Grandes ideas.<br/>De tu comunidad.</h1><p>Escucha las conversaciones. Encuentra lo que importa.<br className="hidden lg:block"/> Transfórmalo en contenido que conecta.</p><Link className="btn-primary" href="/ingesta">Traer conversaciones <ArrowUpRight size={18}/></Link></div>
    <div className="gum-intro-art" aria-hidden="true"><span className="gum-art-star">✳</span><div className="gum-art-message"><MessageSquare size={24}/><div className="gum-art-lines"><i/><i/><i/></div><span>De una conversación…</span></div><ArrowRight className="gum-art-arrow" size={30}/><div className="gum-art-document"><FileText size={24}/><strong>Una nueva<br/>historia.</strong><span><Check size={15}/>Revisión humana</span></div><span className="gum-art-sticker">HECHO EN<br/>COMUNIDAD ↗</span></div>
  </section>;
}
