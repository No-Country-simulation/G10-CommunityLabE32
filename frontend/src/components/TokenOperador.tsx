'use client';

import React from 'react';

interface TokenOperadorProps {
  className?: string;
}

export default function TokenOperador({ className = '' }: TokenOperadorProps) {
  // El sistema de autenticación JWT reconoce tus permisos automáticamente al iniciar sesión.
  return (
    <div className={`text-xs text-muted-foreground flex items-center gap-2 ${className}`}>
      <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block shadow-[0_0_8px_rgba(16,185,129,0.6)]" />
      <span>Sesión de operador activa y verificada por JWT</span>
    </div>
  );
}