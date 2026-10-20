import type { PointerEvent } from 'react';

export function seguirLuz(event: PointerEvent<HTMLElement>) {
  const root = document.documentElement;
  root.style.setProperty('--luz-x', `${event.clientX}px`);
  root.style.setProperty('--luz-y', `${event.clientY}px`);
}
