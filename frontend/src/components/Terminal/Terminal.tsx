import { useEffect, useRef } from 'react';
import type { OutputEntry as OutputEntryType } from '../../types';
import { OutputEntry } from './OutputEntry';
import styles from './Terminal.module.css';

interface TerminalProps {
  outputs: OutputEntryType[];
}

export function Terminal({ outputs }: TerminalProps) {
  const terminalRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [outputs]);

  return (
    <main className={styles.terminal} ref={terminalRef}>
      {outputs.length === 0 ? (
        <div className={styles.emptyState}>
          <p>Select a command to run</p>
        </div>
      ) : (
        outputs.map((entry) => <OutputEntry key={entry.id} entry={entry} />)
      )}
    </main>
  );
}
