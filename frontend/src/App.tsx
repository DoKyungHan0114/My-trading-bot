import { Header, Sidebar, Terminal } from './components';
import { useCommands, useHealth, useKeyboardShortcuts } from './hooks';
import './styles/global.css';

function App() {
  const health = useHealth();
  const { commands, outputs, runningCommand, runCommand, clearOutput } =
    useCommands();

  useKeyboardShortcuts({
    commands,
    runningCommand,
    onRunCommand: runCommand,
    onClearOutput: clearOutput,
  });

  return (
    <div className="app">
      <Header health={health} />
      <div className="main-container">
        <Sidebar
          commands={commands}
          runningCommand={runningCommand}
          onRunCommand={runCommand}
          onClearOutput={clearOutput}
        />
        <Terminal outputs={outputs} />
      </div>
    </div>
  );
}

export default App;
