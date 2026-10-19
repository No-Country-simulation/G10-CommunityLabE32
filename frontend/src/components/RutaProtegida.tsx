'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { obtenerSesion } from '@/services/api';
import { Loader2 } from 'lucide-react';

export default function RutaProtegida({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [autorizado, setAutorizado] = useState(false);

  useEffect(() => {
    // La sesión la decide el servidor (cookie HttpOnly): sin sesión vigente, al login.
    // Es solo navegación: cada endpoint vuelve a exigir sesión y rol en el backend.
    let vigente = true;
    obtenerSesion()
      .then((usuario) => {
        if (!vigente) return;
        if (usuario) setAutorizado(true);
        else router.replace('/login');
      })
      .catch(() => {
        if (vigente) router.replace('/login');
      });
    return () => { vigente = false; };
  }, [router]);

  if (!autorizado) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex items-center gap-3 text-muted-foreground text-sm">
          <Loader2 className="w-5 h-5 animate-spin text-primary" />
          Verificando sesión segura…
        </div>
      </div>
    );
  }

  return <>{children}</>;
}