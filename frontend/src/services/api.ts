import type { Command, HealthStatus } from '../types';

const API_BASE = '/api';

export async function fetchCommands(): Promise<Command[]> {
  const response = await fetch(`${API_BASE}/commands`);
  if (!response.ok) {
    throw new Error(`Failed to fetch commands: ${response.status}`);
  }
  return response.json();
}

export async function fetchHealth(): Promise<HealthStatus | null> {
  try {
    const response = await fetch(`${API_BASE}/health`);
    if (!response.ok) return null;
    const data = await response.json();
    return {
      trading_system: data.trading_system,
      firestore: data.firestore,
    };
  } catch {
    return null;
  }
}

export async function streamCommand(
  commandId: string,
  onChunk: (chunk: string, fullOutput: string) => void
): Promise<number> {
  const response = await fetch(`${API_BASE}/commands/${commandId}/stream`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  if (!reader) {
    throw new Error('No response body');
  }

  let fullOutput = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    fullOutput += chunk;
    onChunk(chunk, fullOutput);
  }

  const exitMatch = fullOutput.match(/\[Exit code: (\d+)\]/);
  return exitMatch ? parseInt(exitMatch[1]) : 0;
}

export function downloadLatestPdf(): void {
  window.open(`${API_BASE}/reports/pdf/latest`, '_blank');
}
