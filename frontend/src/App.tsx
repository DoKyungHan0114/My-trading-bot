import { useState, useEffect, useRef, useCallback } from 'react';
import './index.css';

interface Command {
  id: string;
  name: string;
  description: string;
}

interface OutputEntry {
  id: string;
  commandId: string;
  command: string;
  output: string;
  status: 'running' | 'success' | 'error';
  timestamp: Date;
}

interface HealthStatus {
  trading_system: boolean;
  firestore: boolean;
}

function App() {
  const [commands, setCommands] = useState<Command[]>([]);
  const [outputs, setOutputs] = useState<OutputEntry[]>([]);
  const [runningCommand, setRunningCommand] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const outputRef = useRef<HTMLDivElement>(null);

  const fetchHealth = async () => {
    try {
      const response = await fetch('/api/health');
      if (response.ok) {
        const data = await response.json();
        setHealth({ trading_system: data.trading_system, firestore: data.firestore });
      }
    } catch {
      setHealth(null);
    }
  };

  useEffect(() => {
    fetchCommands();
    fetchHealth();
    const healthInterval = setInterval(fetchHealth, 30000);
    return () => clearInterval(healthInterval);
  }, []);

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [outputs]);

  const fetchCommands = async () => {
    try {
      const response = await fetch('/api/commands');
      if (response.ok) {
        const data = await response.json();
        setCommands(data);
      }
    } catch (error) {
      console.error('Failed to fetch commands:', error);
    }
  };

  const runCommand = async (commandId: string, commandName: string) => {
    if (runningCommand) return;

    const entryId = Date.now().toString();
    setRunningCommand(commandId);

    setOutputs(prev => [...prev, {
      id: entryId,
      commandId,
      command: commandName,
      output: '',
      status: 'running',
      timestamp: new Date(),
    }]);

    try {
      const response = await fetch(`/api/commands/${commandId}/stream`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (reader) {
        let fullOutput = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          fullOutput += chunk;

          setOutputs(prev => prev.map(entry =>
            entry.id === entryId
              ? { ...entry, output: fullOutput }
              : entry
          ));
        }

        const exitMatch = fullOutput.match(/\[Exit code: (\d+)\]/);
        const exitCode = exitMatch ? parseInt(exitMatch[1]) : 0;

        setOutputs(prev => prev.map(entry =>
          entry.id === entryId
            ? { ...entry, status: exitCode === 0 ? 'success' : 'error' }
            : entry
        ));
      }
    } catch (error) {
      setOutputs(prev => prev.map(entry =>
        entry.id === entryId
          ? { ...entry, output: `Error: ${error}`, status: 'error' }
          : entry
      ));
    } finally {
      setRunningCommand(null);
    }
  };

  const downloadLatestPdf = () => {
    window.open('/api/reports/pdf/latest', '_blank');
  };

  const clearOutput = useCallback(() => {
    setOutputs([]);
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if typing in input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      // Esc - clear output
      if (e.key === 'Escape') {
        clearOutput();
        return;
      }

      // 1-9 - run command by index
      const num = parseInt(e.key);
      if (num >= 1 && num <= 9 && commands[num - 1] && !runningCommand) {
        const cmd = commands[num - 1];
        runCommand(cmd.id, cmd.name);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [commands, runningCommand, clearOutput]);

  return (
    <div className="app">
      <header className="header">
        <h1>TQQQ Trading System</h1>
        <span className="subtitle">Command Runner</span>
        <div className="health-status">
          <span className={`health-dot ${health?.trading_system ? 'ok' : 'err'}`} />
          <span className="health-label">Trading</span>
          <span className={`health-dot ${health?.firestore ? 'ok' : 'err'}`} />
          <span className="health-label">Firestore</span>
        </div>
      </header>

      <div className="main-container">
        <aside className="sidebar">
          <h2>Commands</h2>
          <div className="command-list">
            {commands.map((cmd, idx) => (
              <button
                key={cmd.id}
                className={`command-btn ${runningCommand === cmd.id ? 'running' : ''}`}
                onClick={() => runCommand(cmd.id, cmd.name)}
                disabled={runningCommand !== null}
                title={`${cmd.description} [${idx + 1}]`}
              >
                <span className="command-key">{idx + 1}</span>
                <div className="command-info">
                  <span className="command-name">{cmd.name}</span>
                  <span className="command-desc">{cmd.description}</span>
                </div>
              </button>
            ))}
          </div>
          <button className="clear-btn" onClick={clearOutput}>
            <span className="command-key">Esc</span>
            Clear Output
          </button>
        </aside>

        <main className="terminal" ref={outputRef}>
          {outputs.length === 0 ? (
            <div className="empty-state">
              <p>Select a command to run</p>
            </div>
          ) : (
            outputs.map(entry => (
              <div key={entry.id} className={`output-entry ${entry.status}`}>
                <div className="output-header">
                  <span className="prompt">$</span>
                  <span className="command-text">{entry.command}</span>
                  <span className="timestamp">
                    {entry.timestamp.toLocaleTimeString()}
                  </span>
                  {entry.status === 'running' && (
                    <span className="status-badge running">Running...</span>
                  )}
                  {entry.status === 'success' && (
                    <span className="status-badge success">Done</span>
                  )}
                  {entry.status === 'error' && (
                    <span className="status-badge error">Error</span>
                  )}
                  {entry.status === 'success' && entry.commandId === 'backtest' && (
                    <button className="download-btn" onClick={downloadLatestPdf}>
                      Download PDF
                    </button>
                  )}
                </div>
                <pre className="output-content">{entry.output}</pre>
              </div>
            ))
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
