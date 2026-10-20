'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { leerTokenOperador } from '@/services/api';
import { esVistaLocal } from '@/services/vistaLocal';
import { Loader2 } from 'lucide-react';

export default function RutaProtegida({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [autorizado, setAutorizado] = useState(false);

  useEffect(() => {
    const token = leerTokenOperador();
    if (!token && !esVistaLocal()) {
      router.replace('/login');
    } else {
      // Usamos un setTimeout para evitar el setState sincrónico dentro del effect que rechaza ESLint
      const timer = setTimeout(() => {
        setAutorizado(true);
      }, 0);
      return () => clearTimeout(timer);
    }
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
