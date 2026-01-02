import { useState, useEffect, useCallback } from 'react';
import type { Command, OutputEntry } from '../types';
import { fetchCommands as fetchCommandsApi, streamCommand } from '../services/api';

export function useCommands() {
  const [commands, setCommands] = useState<Command[]>([]);
  const [outputs, setOutputs] = useState<OutputEntry[]>([]);
  const [runningCommand, setRunningCommand] = useState<string | null>(null);

  useEffect(() => {
    fetchCommandsApi()
      .then(setCommands)
      .catch((error) => console.error('Failed to fetch commands:', error));
  }, []);

  const runCommand = useCallback(async (commandId: string, commandName: string) => {
    if (runningCommand) return;

    const entryId = Date.now().toString();
    setRunningCommand(commandId);

    setOutputs((prev) => [
      ...prev,
      {
        id: entryId,
        commandId,
        command: commandName,
        output: '',
        status: 'running',
        timestamp: new Date(),
      },
    ]);

    try {
      const exitCode = await streamCommand(commandId, (_chunk, fullOutput) => {
        setOutputs((prev) =>
          prev.map((entry) =>
            entry.id === entryId ? { ...entry, output: fullOutput } : entry
          )
        );
      });

      setOutputs((prev) =>
        prev.map((entry) =>
          entry.id === entryId
            ? { ...entry, status: exitCode === 0 ? 'success' : 'error' }
            : entry
        )
      );
    } catch (error) {
      setOutputs((prev) =>
        prev.map((entry) =>
          entry.id === entryId
            ? { ...entry, output: `Error: ${error}`, status: 'error' }
            : entry
        )
      );
    } finally {
      setRunningCommand(null);
    }
  }, [runningCommand]);

  const clearOutput = useCallback(() => {
    setOutputs([]);
  }, []);

  return {
    commands,
    outputs,
    runningCommand,
    runCommand,
    clearOutput,
  };
}
