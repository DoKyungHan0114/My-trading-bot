import type { Command } from '../../types';
import { CommandButton } from './CommandButton';
import styles from './Sidebar.module.css';

interface SidebarProps {
  commands: Command[];
  runningCommand: string | null;
  onRunCommand: (commandId: string, commandName: string) => void;
  onClearOutput: () => void;
}

export function Sidebar({
  commands,
  runningCommand,
  onRunCommand,
  onClearOutput,
}: SidebarProps) {
  return (
    <aside className={styles.sidebar}>
      <h2 className={styles.sectionTitle}>Commands</h2>
      <div className={styles.commandList}>
        {commands.map((cmd, idx) => (
          <CommandButton
            key={cmd.id}
            command={cmd}
            index={idx}
            isRunning={runningCommand === cmd.id}
            isDisabled={runningCommand !== null}
            onRun={onRunCommand}
          />
        ))}
      </div>
      <button className={styles.clearBtn} onClick={onClearOutput}>
        <span className={styles.clearKey}>Esc</span>
        Clear Output
      </button>
    </aside>
  );
}
