import { useEffect } from 'react';
import type { Command } from '../types';

interface UseKeyboardShortcutsOptions {
  commands: Command[];
  runningCommand: string | null;
  onRunCommand: (commandId: string, commandName: string) => void;
  onClearOutput: () => void;
}

export function useKeyboardShortcuts({
  commands,
  runningCommand,
  onRunCommand,
  onClearOutput,
}: UseKeyboardShortcutsOptions) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      if (e.key === 'Escape') {
        onClearOutput();
        return;
      }

      const num = parseInt(e.key);
      if (num >= 1 && num <= 9 && commands[num - 1] && !runningCommand) {
        const cmd = commands[num - 1];
        onRunCommand(cmd.id, cmd.name);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [commands, runningCommand, onRunCommand, onClearOutput]);
}
