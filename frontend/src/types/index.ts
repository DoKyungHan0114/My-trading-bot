export interface Command {
  id: string;
  name: string;
  description: string;
}

export interface OutputEntry {
  id: string;
  commandId: string;
  command: string;
  output: string;
  status: 'running' | 'success' | 'error';
  timestamp: Date;
}

export interface HealthStatus {
  trading_system: boolean;
  firestore: boolean;
}
