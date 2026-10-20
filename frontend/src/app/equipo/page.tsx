'use client';

import {
  Users,
  Globe,
  Code2,
  Database,
  Cpu,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { motion } from 'framer-motion';
import Sidebar from '@/components/Sidebar';
import RutaProtegida from '@/components/RutaProtegida';

function IconoLinkedin({ className = 'w-3.5 h-3.5' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.28 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.75M6.88 8.56a1.68 1.68 0 0 0 1.68-1.68c0-.93-.75-1.69-1.68-1.69a1.69 1.69 0 0 0-1.69 1.69c0 .93.76 1.68 1.69 1.68m1.39 9.94v-8.37H5.5v8.37h2.77z" />
    </svg>
  );
}

function IconoGithub({ className = 'w-3.5 h-3.5' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2A10 10 0 0 0 2 12c0 4.42 2.87 8.17 6.84 9.5.5.08.66-.23.66-.5v-1.69c-2.77.6-3.36-1.34-3.36-1.34-.46-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.87 1.52 2.34 1.07 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.92 0-1.11.38-2 1.03-2.71-.1-.25-.45-1.29.1-2.64 0 0 .84-.27 2.75 1.02.79-.22 1.65-.33 2.5-.33.85 0 1.71.11 2.5.33 1.91-1.29 2.75-1.02 2.75-1.02.55 1.35.2 2.39.1 2.64.65.71 1.03 1.6 1.03 2.71 0 3.82-2.34 4.66-4.57 4.91.36.31.69.92.69 1.85V21c0 .27.16.59.67.5C19.14 20.16 22 16.42 22 12A10 10 0 0 0 12 2z" />
    </svg>
  );
}

interface MiembroEquipo {
  nombre: string;
  iniciales: string;
  rol: string;
  especialidad: string;
  bio: string;
  stack: string[];
  colorGradiente: string;
  linkedin: string;
}

const integrantes: MiembroEquipo[] = [
  {
    nombre: 'ianjaner alfonso beltran guañarita',
    iniciales: 'IB',
    rol: 'Full Stack Developer',
    especialidad: 'Next.js 16 • UI/UX • Autenticación JWT & FastAPI',
    bio: 'Desarrollo de la interfaz de usuario, Centro de Operaciones, seguridad JWT y protección de rutas en el ecosistema del frontend.',
    stack: ['Next.js 16', 'TypeScript', 'Tailwind', 'FastAPI', 'PostgreSQL'],
    colorGradiente: 'from-cyan-500 to-blue-600',
    linkedin: 'https://www.linkedin.com/in/ianjaner-beltran/',
  },
  {
    nombre: 'Paulo Andres Escobar Solorzano',
    iniciales: 'PE',
    rol: 'Autonomous Agent Engineer',
    especialidad: 'LangGraph • Gemini AI • Infraestructura VM',
    bio: 'Arquitectura de agentes autónomos con Gemini, integración con Discord y despliegue backend.',
    stack: ['Python', 'LangGraph', 'Gemini API', 'Docker', 'Nginx'],
    colorGradiente: 'from-violet-500 to-indigo-600',
    linkedin: 'https://www.linkedin.com/in/paulo-escobar-nodnexa/',
  },
  {
    nombre: 'Fredy Pachon',
    iniciales: 'FP',
    rol: 'Backend Developer',
    especialidad: 'Científico de Datos • Modelado y Lógica',
    bio: 'Construcción y validación de flujos de datos analíticos y soporte en la lógica del backend.',
    stack: ['Python', 'SQLAlchemy', 'Data Science', 'FastAPI'],
    colorGradiente: 'from-amber-500 to-orange-600',
    linkedin: 'https://www.linkedin.com/in/fredy-pachon-cinetifico-datos/',
  },
  {
    nombre: 'santiago Horta Hurtado',
    iniciales: 'SH',
    rol: 'Autonomous Agent Engineer',
    especialidad: 'Agentes Inteligentes • Integración Backend',
    bio: 'Desarrollo y optimización de componentes de automatización y lógica de agentes de inteligencia artificial.',
    stack: ['Python', 'IA', 'FastAPI', 'Git'],
    colorGradiente: 'from-emerald-500 to-teal-600',
    linkedin: 'https://www.linkedin.com/in/santiago-h-4bb592109/',
  },
  {
    nombre: 'Fabian Hernández Alejandro',
    iniciales: 'FH',
    rol: 'Prompt Engineer',
    especialidad: 'Ingeniería de Prompts • Modelos LLM',
    bio: 'Diseño, prueba y optimización de prompts estructurados para el análisis de sentimiento y generación de contenido editorial.',
    stack: ['Prompt Engineering', 'Gemini AI', 'JSON Schema', 'NLP'],
    colorGradiente: 'from-blue-500 to-cyan-600',
    linkedin: 'https://www.linkedin.com/in/fabián-hernández-alejandro/',
  },
  {
    nombre: 'Jose Angel Olan de los Santos',
    iniciales: 'JO',
    rol: 'Data Engineer',
    especialidad: 'PostgreSQL • Modelado de Datos • ETL',
    bio: 'Estructuración de esquemas relacionales, optimización de consultas asíncronas y gestión de bases de datos.',
    stack: ['PostgreSQL', 'SQLAlchemy', 'Python', 'Docker'],
    colorGradiente: 'from-rose-500 to-pink-600',
    linkedin: 'https://www.linkedin.com/in/jose-olan/',
  },
  {
    nombre: 'Vania Sherel Cruz Hernandez',
    iniciales: 'VC',
    rol: 'Vibe Coder',
    especialidad: 'Experiencia de Usuario • Soporte de Integración',
    bio: 'Colaboración en el desarrollo del flujo frontend, pruebas y refinamiento general de la experiencia de la plataforma.',
    stack: ['Frontend', 'JavaScript', 'Tailwind', 'UI Testing'],
    colorGradiente: 'from-fuchsia-500 to-purple-600',
    linkedin: 'https://www.linkedin.com/in/vaniasherelcruz/',
  },
  {
    nombre: 'Elizabeth Aguilar',
    iniciales: 'EA',
    rol: 'Project Manager',
    especialidad: 'Gestión de Proyecto • Metodologías Ágiles • QA',
    bio: 'Coordinación general del equipo de trabajo en No Country, planificación de sprints y control de calidad para el Demo Day.',
    stack: ['Agile', 'Scrum', 'Jira', 'QA Management'],
    colorGradiente: 'from-yellow-500 to-amber-600',
    linkedin: 'https://www.linkedin.com/in/eav1804/',
  },
];

const pilaresArquitectura = [
  {
    titulo: 'Ingesta Multimodal y Puente Discord',
    descripcion: 'Captura conversaciones reales desde Discord y archivos JSON/CSV con validación estricta e idempotencia.',
    icono: Code2,
  },
  {
    titulo: 'Grafo de Agentes IA con Gemini',
    descripcion: 'Clasifica logros, dudas recurrentes y bloqueos, generando borradores con control automático de fidelidad.',
    icono: Cpu,
  },
  {
    titulo: 'Persistencia Asíncrona en PostgreSQL',
    descripcion: 'Consultas parametrizadas O(1) en memoria RAM con SQLAlchemy 2.0 y cola de trabajos resiliente.',
    icono: Database,
  },
  {
    titulo: 'Curaduría Ética y Seguridad JWT',
    descripcion: 'Revisión humana obligatoria, protección de identidad del autor y acceso blindado con tokens JWT y Bcrypt.',
    icono: ShieldCheck,
  },
];

export default function EquipoPage() {
  return (
    <RutaProtegida>
      <div className="flex min-h-screen w-full">
        <Sidebar />

        <main className="flex-1 min-w-0 p-4 sm:p-6 md:p-10 md:h-[calc(100dvh-var(--topbar-h))] md:overflow-y-auto">
          <header className="mb-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary-soft text-primary text-xs font-bold mb-2">
              <Sparkles className="w-3.5 h-3.5" /> No Country • Simulación G10 — Equipo 32
            </div>
            <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-foreground">
              El Equipo detrás de CommunityLab
            </h1>
            <p className="text-muted-foreground text-[15px] mt-2 max-w-3xl leading-relaxed">
              Somos un equipo multidisciplinario de ingeniería de software e inteligencia artificial enfocado en transformar el ruido de las comunidades digitales en conocimiento estructurado, accionable y éticamente curado.
            </p>
          </header>

          <section className="mb-12">
            <h2 className="text-lg font-bold text-foreground mb-5 flex items-center gap-2">
              <Users className="w-5 h-5 text-primary" /> Integrantes y Roles
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {integrantes.map((m, idx) => (
                <motion.div
                  key={`${m.nombre}-${idx}`}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className="card p-6 flex flex-col justify-between hover:shadow-lg hover:border-border-strong transition-all"
                >
                  <div>
                    <div className="flex items-start justify-between gap-4 mb-4">
                      <div className="flex items-center gap-3.5">
                        <div
                          className={`w-12 h-12 rounded-2xl bg-gradient-to-br ${m.colorGradiente} flex items-center justify-center text-white font-extrabold text-lg shadow-md shrink-0`}
                        >
                          {m.iniciales}
                        </div>
                        <div>
                          <h3 className="text-lg font-bold text-foreground">{m.nombre}</h3>
                          <p className="text-xs font-semibold text-primary">{m.rol}</p>
                          <p className="text-[11px] text-subtle-foreground mt-0.5">{m.especialidad}</p>
                        </div>
                      </div>
                    </div>

                    <p className="text-sm text-muted-foreground leading-relaxed mb-5">{m.bio}</p>

                    <div className="flex flex-wrap gap-1.5 mb-6">
                      {m.stack.map((tech) => (
                        <span key={tech} className="badge-neutral text-[11px]">
                          {tech}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="pt-4 border-t border-border flex items-center gap-3">
                    <a
                      href={m.linkedin}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn-secondary py-1.5! px-3! text-xs flex items-center gap-1.5"
                    >
                      <IconoLinkedin className="w-3.5 h-3.5 text-info" />
                      LinkedIn
                    </a>
                  </div>
                </motion.div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="text-lg font-bold text-foreground mb-4">
              Arquitectura e Innovación del Proyecto
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
              {pilaresArquitectura.map((pilar) => {
                const Icono = pilar.icono;
                return (
                  <div key={pilar.titulo} className="card p-5">
                    <div className="w-9 h-9 rounded-lg bg-primary-soft text-primary flex items-center justify-center mb-3">
                      <Icono className="w-5 h-5" />
                    </div>
                    <h3 className="text-sm font-bold text-foreground mb-1.5">{pilar.titulo}</h3>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {pilar.descripcion}
                    </p>
                  </div>
                );
              })}
            </div>
          </section>
        </main>
      </div>
    </RutaProtegida>
  );
}