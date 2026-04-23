import { useEffect } from 'react';

/**
 * Register a global keyboard shortcut. Handles Cmd on mac and Ctrl on other
 * platforms transparently. Matches the key case-insensitively.
 *
 * Shortcuts are ignored while the user is typing into an input, textarea, or
 * contenteditable — except when ``allowInEditable`` is set (e.g. Cmd+Enter
 * while in a composer textarea).
 *
 * Example:
 *   useHotkey({ mod: true, key: 'k' }, () => navigate('/'))
 *   useHotkey({ mod: true, key: 'Enter', allowInEditable: true }, submit)
 */
export interface Hotkey {
  key: string;
  mod?: boolean; // Cmd/Ctrl
  shift?: boolean;
  allowInEditable?: boolean;
}

function isEditable(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (el.isContentEditable) return true;
  return false;
}

export function useHotkey(
  hotkey: Hotkey,
  handler: (e: KeyboardEvent) => void,
  deps: React.DependencyList = [],
) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const modOk = hotkey.mod ? e.metaKey || e.ctrlKey : !e.metaKey && !e.ctrlKey;
      const shiftOk = hotkey.shift ? e.shiftKey : !e.shiftKey;
      const keyOk = e.key.toLowerCase() === hotkey.key.toLowerCase();
      if (!modOk || !shiftOk || !keyOk) return;
      if (!hotkey.allowInEditable && isEditable(e.target)) return;
      e.preventDefault();
      handler(e);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
