'use client';

import React, { useEffect, useState } from 'react';
import { EVENTO_SESION, esOperador, obtenerSesion, usuarioEnMemoria, type UsuarioAuth } from '@/services/api';

interface TokenOperadorProps {
  className?: string;
}

export default function TokenOperador({ className = '' }: TokenOperadorProps) {
  // Los permisos vienen del rol de la sesión (cookie HttpOnly); aquí solo se muestran.
  const [usuario, setUsuario] = useState<UsuarioAuth | null>(usuarioEnMemoria());
  useEffect(() => {
    const actualizar = () => setUsuario(usuarioEnMemoria());
    window.addEventListener(EVENTO_SESION, actualizar);
    if (!usuarioEnMemoria()) obtenerSesion().catch(() => {});
    return () => window.removeEventListener(EVENTO_SESION, actualizar);
  }, []);
  const operador = esOperador(usuario);
  return (
    <div className={`text-xs text-muted-foreground flex items-center gap-2 ${className}`}>
      <span className={`w-2 h-2 rounded-full inline-block ${operador
        ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]' : 'bg-amber-500'}`} />
      <span>{operador
        ? `Sesión de ${usuario?.rol} activa`
        : 'Tu cuenta no tiene rol de operador: las acciones quedarán deshabilitadas en el servidor'}</span>
    </div>
  );
}
