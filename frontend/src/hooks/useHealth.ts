import { useState, useEffect } from 'react';
import type { HealthStatus } from '../types';
import { fetchHealth } from '../services/api';

const HEALTH_CHECK_INTERVAL = 30000;

export function useHealth() {
  const [health, setHealth] = useState<HealthStatus | null>(null);

  useEffect(() => {
    fetchHealth().then(setHealth);

    const interval = setInterval(() => {
      fetchHealth().then(setHealth);
    }, HEALTH_CHECK_INTERVAL);

    return () => clearInterval(interval);
  }, []);

  return health;
}
