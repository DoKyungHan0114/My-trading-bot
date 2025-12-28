import { useState, useEffect, useRef } from 'react';
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

function App() {
  const [commands, setCommands] = useState<Command[]>([]);
  const [outputs, setOutputs] = useState<OutputEntry[]>([]);
  const [runningCommand, setRunningCommand] = useState<string | null>(null);
  const outputRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchCommands();
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

  const clearOutput = () => {
    setOutputs([]);
  };

  return (
    <div className="app">
      <header className="header">
        <h1>TQQQ Trading System</h1>
        <span className="subtitle">Command Runner</span>
      </header>

      <div className="main-container">
        <aside className="sidebar">
          <h2>Commands</h2>
          <div className="command-list">
            {commands.map(cmd => (
              <button
                key={cmd.id}
                className={`command-btn ${runningCommand === cmd.id ? 'running' : ''}`}
                onClick={() => runCommand(cmd.id, cmd.name)}
                disabled={runningCommand !== null}
                title={cmd.description}
              >
                <span className="command-name">{cmd.name}</span>
                <span className="command-desc">{cmd.description}</span>
              </button>
            ))}
          </div>
          <button className="clear-btn" onClick={clearOutput}>
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
