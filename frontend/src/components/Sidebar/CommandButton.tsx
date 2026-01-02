import type { Command } from '../../types';
import styles from './Sidebar.module.css';

interface CommandButtonProps {
  command: Command;
  index: number;
  isRunning: boolean;
  isDisabled: boolean;
  onRun: (commandId: string, commandName: string) => void;
}

export function CommandButton({
  command,
  index,
  isRunning,
  isDisabled,
  onRun,
}: CommandButtonProps) {
  return (
    <button
      className={`${styles.commandBtn} ${isRunning ? styles.running : ''}`}
      onClick={() => onRun(command.id, command.name)}
      disabled={isDisabled}
      title={`${command.description} [${index + 1}]`}
    >
      <span className={styles.commandKey}>{index + 1}</span>
      <div className={styles.commandInfo}>
        <span className={styles.commandName}>{command.name}</span>
        <span className={styles.commandDesc}>{command.description}</span>
      </div>
    </button>
  );
}
