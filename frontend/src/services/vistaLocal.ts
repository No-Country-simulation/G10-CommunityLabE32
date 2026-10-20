// Vista del frontend sin sesión: únicamente en desarrollo y en loopback.
export function esVistaLocal(): boolean {
  return process.env.NODE_ENV === 'development'
    && process.env.NEXT_PUBLIC_VISTA_LOCAL === 'true'
    && typeof window !== 'undefined'
    && ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname);
}
