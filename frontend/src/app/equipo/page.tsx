'use client';


import UiTree from '@/components/UiTree';
import {
  Users,
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
  return <UiTree>{(
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.28 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.75M6.88 8.56a1.68 1.68 0 0 0 1.68-1.68c0-.93-.75-1.69-1.68-1.69a1.69 1.69 0 0 0-1.69 1.69c0 .93.76 1.68 1.69 1.68m1.39 9.94v-8.37H5.5v8.37h2.77z" />
    </svg>
  )}</UiTree>;
}

interface MiembroEquipo {
  nombre: string;
  rol: string;
  especialidad: string;
  bio: string;
  stack: string[];
  linkedin: string;
}

const integrantes: MiembroEquipo[] = [
  {
    nombre: 'Elizabeth Aguilar',
    rol: 'Project Manager',
    especialidad: 'Gestión del proyecto • Metodologías ágiles • Control de calidad',
    bio: 'Coordinación general del equipo de trabajo en No Country, planificación de ciclos de trabajo y control de calidad para la presentación del proyecto.',
    stack: ['Agile', 'Scrum', 'Jira', 'QA Management'],
    linkedin: 'https://www.linkedin.com/in/eav1804/',
  },
  {
    nombre: 'Vania Sherel Cruz Hernandez',
    rol: 'Vibe Coder',
    especialidad: 'Experiencia de usuario • Soporte de integración',
    bio: 'Colaboración en el desarrollo del flujo frontend, pruebas y refinamiento general de la experiencia de la plataforma.',
    stack: ['Frontend', 'JavaScript', 'Tailwind', 'UI Testing'],
    linkedin: 'https://www.linkedin.com/in/vaniasherelcruz/',
  },
  {
    nombre: 'Jose Angel Olan de los Santos',
    rol: 'Data Engineer',
    especialidad: 'PostgreSQL • Modelado de datos • ETL',
    bio: 'Estructuración de esquemas relacionales, optimización de consultas asíncronas y gestión de bases de datos.',
    stack: ['PostgreSQL', 'SQLAlchemy', 'Python', 'Docker'],
    linkedin: 'https://www.linkedin.com/in/jose-olan/',
  },
  {
    nombre: 'Fredy Pachon',
    rol: 'Backend Developer',
    especialidad: 'Ciencia de datos • Modelado y lógica',
    bio: 'Construcción y validación de flujos de datos analíticos y soporte en la lógica del backend.',
    stack: ['Python', 'SQLAlchemy', 'Data Science', 'FastAPI'],
    linkedin: 'https://www.linkedin.com/in/fredy-pachon-cinetifico-datos/',
  },
  {
    nombre: 'Ianjaner Alfonso Beltran Guañarita',
    rol: 'Full Stack Developer',
    especialidad: 'Next.js 16 • UI/UX • Autenticación JWT y FastAPI',
    bio: 'Desarrollo de la interfaz de usuario, el centro de operaciones, la seguridad JWT y la protección de rutas en el ecosistema del frontend.',
    stack: ['Next.js 16', 'TypeScript', 'Tailwind', 'FastAPI', 'PostgreSQL'],
    linkedin: 'https://www.linkedin.com/in/ianjaner-beltran/',
  },
  {
    nombre: 'Santiago Horta Hurtado',
    rol: 'Autonomous Agent Engineer',
    especialidad: 'Agentes inteligentes • Integración con el backend',
    bio: 'Desarrollo y optimización de componentes de automatización y lógica de agentes de inteligencia artificial.',
    stack: ['Python', 'IA', 'FastAPI', 'Git'],
    linkedin: 'https://www.linkedin.com/in/santiago-h-4bb592109/',
  },
  {
    nombre: 'Fabián Hernández Alejandro',
    rol: 'Prompt Engineer',
    especialidad: 'Ingeniería de prompts • Modelos LLM',
    bio: 'Diseño, prueba y optimización de prompts estructurados para el análisis de sentimiento y la generación de contenido editorial.',
    stack: ['Prompt Engineering', 'Gemini AI', 'JSON Schema', 'NLP'],
    linkedin: 'https://www.linkedin.com/in/fabián-hernández-alejandro/',
  },
  {
    nombre: 'Paulo Andrés Escobar Saldaña',
    rol: 'Autonomous Agent Engineer',
    especialidad: 'LangGraph • Gemini AI • Infraestructura de máquinas virtuales',
    bio: 'Arquitectura de agentes autónomos con Gemini, integración con Discord y despliegue del backend.',
    stack: ['Python', 'LangGraph', 'Gemini API', 'Docker', 'Nginx', 'Claude Code', 'Codex'],
    linkedin: 'https://www.linkedin.com/in/paulo-escobar-nodnexa/',
  },
];

const pilaresArquitectura = [
  {
    titulo: 'Ingesta multimodal y puente de Discord',
    descripcion: 'Captura conversaciones reales desde Discord y archivos JSON/CSV con validación estricta e idempotencia.',
    icono: Code2,
  },
  {
    titulo: 'Grafo de agentes de IA con Gemini',
    descripcion: 'Clasifica logros, dudas recurrentes y bloqueos, generando borradores con control automático de fidelidad.',
    icono: Cpu,
  },
  {
    titulo: 'Persistencia asíncrona en PostgreSQL',
    descripcion: 'Consultas parametrizadas O(1) en memoria RAM con SQLAlchemy 2.0 y cola de trabajos resiliente.',
    icono: Database,
  },
  {
    titulo: 'Curaduría ética y seguridad JWT',
    descripcion: 'Revisión obligatoria, protección de identidad del autor y acceso blindado con tokens JWT y Bcrypt.',
    icono: ShieldCheck,
  },
];

export default function EquipoPage() {
  return <UiTree>{(
    <RutaProtegida>
      <div className="flex min-h-screen w-full">
        <Sidebar />

        <main className="dashboard-content flex-1 min-w-0 p-4 sm:p-6 md:p-10 md:h-[calc(100dvh-var(--topbar-h))] md:overflow-y-auto">
          <header className="mb-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary-soft text-primary text-xs font-bold mb-2">
              <Sparkles className="w-3.5 h-3.5" /> Equipo 32
            </div>
            <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-foreground">
              El equipo detrás de CommunityLab
            </h1>
            <p className="text-muted-foreground text-[15px] mt-2 max-w-3xl leading-relaxed">
              Somos un equipo multidisciplinario de ingeniería de software e inteligencia artificial enfocado en transformar el ruido de las comunidades digitales en conocimiento estructurado, útil y revisado con criterios éticos.
            </p>
          </header>

          <section className="mb-12">
            <h2 className="text-lg font-bold text-foreground mb-5 flex items-center gap-2">
              <Users className="w-5 h-5 text-primary" /> Integrantes y roles
            </h2>

            <div className="team-members-grid grid grid-cols-1 md:grid-cols-2 gap-6">
              {integrantes.map((m, idx) => (
                <motion.div
                  key={`${m.nombre}-${idx}`}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className="card p-6 flex flex-col justify-between hover:shadow-lg hover:border-border-strong transition-all"
                >
                  <div>
                    <div className="team-member-heading mb-4">
                          <h3 className="team-member-name text-foreground" translate="no">{m.nombre}</h3>
                          <p className="text-xs font-semibold text-primary">{m.rol}</p>
                          <p className="text-[11px] text-subtle-foreground mt-0.5">{m.especialidad}</p>

                    </div>

                    <p className="text-sm text-muted-foreground leading-relaxed mb-5">{m.bio}</p>

                    <div className="flex flex-wrap gap-1.5 mb-6">
                      {m.stack.map((tech) => (
                        <span key={tech} className="team-skill badge-neutral text-[11px]">
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
                      className="team-linkedin btn-secondary py-1.5! px-3! text-xs flex items-center gap-1.5"
                    >
                      <IconoLinkedin className="team-linkedin-icon w-4 h-4" />
                      LinkedIn
                    </a>
                  </div>
                </motion.div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="text-lg font-bold text-foreground mb-4">
              Arquitectura e innovación del proyecto
            </h2>
            <div className="team-architecture-grid grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
              {pilaresArquitectura.map((pilar) => {
                const Icono = pilar.icono;
                return <UiTree key={pilar.titulo}>{(
                  <div key={pilar.titulo} className="card p-5">
                    <div className="w-9 h-9 rounded-lg bg-primary-soft text-primary flex items-center justify-center mb-3">
                      <Icono className="w-5 h-5" />
                    </div>
                    <h3 className="text-sm font-bold text-foreground mb-1.5">{pilar.titulo}</h3>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {pilar.descripcion}
                    </p>
                  </div>
                )}</UiTree>;
              })}
            </div>
          </section>
        </main>
      </div>
    </RutaProtegida>
  )}</UiTree>;
}