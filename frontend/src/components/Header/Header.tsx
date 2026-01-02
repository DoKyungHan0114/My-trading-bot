import type { HealthStatus } from '../../types';
import styles from './Header.module.css';

interface HeaderProps {
  health: HealthStatus | null;
}

export function Header({ health }: HeaderProps) {
  return (
    <header className={styles.header}>
      <h1 className={styles.title}>TQQQ Trading System</h1>
      <span className={styles.subtitle}>Command Runner</span>
      <div className={styles.healthStatus}>
        <HealthIndicator label="Trading" isHealthy={health?.trading_system} />
        <HealthIndicator label="Firestore" isHealthy={health?.firestore} />
      </div>
    </header>
  );
}

interface HealthIndicatorProps {
  label: string;
  isHealthy?: boolean;
}

function HealthIndicator({ label, isHealthy }: HealthIndicatorProps) {
  return (
    <>
      <span
        className={`${styles.healthDot} ${isHealthy ? styles.ok : styles.err}`}
      />
      <span className={styles.healthLabel}>{label}</span>
    </>
  );
}
