import type { OutputEntry as OutputEntryType } from '../../types';
import { downloadLatestPdf } from '../../services/api';
import styles from './Terminal.module.css';

interface OutputEntryProps {
  entry: OutputEntryType;
}

export function OutputEntry({ entry }: OutputEntryProps) {
  return (
    <div className={`${styles.outputEntry} ${styles[entry.status]}`}>
      <div className={styles.outputHeader}>
        <span className={styles.prompt}>$</span>
        <span className={styles.commandText}>{entry.command}</span>
        <span className={styles.timestamp}>
          {entry.timestamp.toLocaleTimeString()}
        </span>
        <StatusBadge status={entry.status} />
        {entry.status === 'success' && entry.commandId === 'backtest' && (
          <button className={styles.downloadBtn} onClick={downloadLatestPdf}>
            Download PDF
          </button>
        )}
      </div>
      <pre className={styles.outputContent}>{entry.output}</pre>
    </div>
  );
}

interface StatusBadgeProps {
  status: 'running' | 'success' | 'error';
}

function StatusBadge({ status }: StatusBadgeProps) {
  const labels = {
    running: 'Running...',
    success: 'Done',
    error: 'Error',
  };

  return (
    <span className={`${styles.statusBadge} ${styles[status]}`}>
      {labels[status]}
    </span>
  );
}
