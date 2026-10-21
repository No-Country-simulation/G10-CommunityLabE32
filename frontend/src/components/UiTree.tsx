'use client';
import { Children, cloneElement, isValidElement, type ReactNode } from 'react';
import useAuthLanguage from './useAuthLanguage';
import { translateText } from '@/i18n/translate';

// Translate React text and accessible labels without changing data or form values.
export default function UiTree({ children }: { children: ReactNode }) {
  const { language } = useAuthLanguage();
  function visit(node: ReactNode): ReactNode {
    if (typeof node === 'string') return translateText(node, language);
    if (Array.isArray(node)) return Children.map(node, visit);
    if (!isValidElement<Record<string, unknown>>(node)) return node;
    const props = node.props;
    if (props.translate === 'no' || (typeof node.type === 'string' && ['code', 'pre', 'kbd', 'samp'].includes(node.type))) return node;
    const changes: Record<string, unknown> = {};
    for (const key of ['title', 'placeholder', 'aria-label', 'alt']) if (typeof props[key] === 'string') changes[key] = translateText(props[key], language);
    if ('children' in props) changes.children = visit(props.children as ReactNode);
    return cloneElement(node, changes);
  }
  return <>{visit(children)}</>;
}
