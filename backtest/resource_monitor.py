"""
Resource usage monitoring for backtests.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ResourceUsage:
    """Resource usage metrics."""
    execution_time_seconds: float = 0.0
    peak_memory_mb: float = 0.0
    avg_memory_mb: float = 0.0
    api_calls: int = 0
    data_points_processed: int = 0
    trades_executed: int = 0

    # Cost estimation (approximate cloud costs)
    estimated_compute_cost_usd: float = 0.0
    estimated_api_cost_usd: float = 0.0
    estimated_storage_cost_usd: float = 0.0

    @property
    def total_estimated_cost_usd(self) -> float:
        """Total estimated cloud cost."""
        return (
            self.estimated_compute_cost_usd +
            self.estimated_api_cost_usd +
            self.estimated_storage_cost_usd
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "execution_time_seconds": round(self.execution_time_seconds, 2),
            "peak_memory_mb": round(self.peak_memory_mb, 2),
            "avg_memory_mb": round(self.avg_memory_mb, 2),
            "api_calls": self.api_calls,
            "data_points_processed": self.data_points_processed,
            "trades_executed": self.trades_executed,
            "estimated_compute_cost_usd": round(self.estimated_compute_cost_usd, 4),
            "estimated_api_cost_usd": round(self.estimated_api_cost_usd, 4),
            "estimated_storage_cost_usd": round(self.estimated_storage_cost_usd, 4),
            "total_estimated_cost_usd": round(self.total_estimated_cost_usd, 4),
        }

    def format_summary(self) -> str:
        """Format as human-readable summary."""
        return (
            f"⏱️ Execution Time: {self.execution_time_seconds:.2f}s\n"
            f"💾 Peak Memory: {self.peak_memory_mb:.1f}MB\n"
            f"📊 Data Points: {self.data_points_processed:,}\n"
            f"🔄 API Calls: {self.api_calls}\n"
            f"📈 Trades: {self.trades_executed}\n"
            f"💰 Est. Cost: ${self.total_estimated_cost_usd:.4f}"
        )


class ResourceMonitor:
    """Monitor resource usage during backtest execution."""

    # Cost rates (approximate)
    COMPUTE_COST_PER_HOUR_USD = 0.05  # Small VM
    API_COST_PER_CALL_USD = 0.0001  # Alpaca is free, but estimate for other APIs
    STORAGE_COST_PER_MB_USD = 0.00003  # S3-like pricing

    def __init__(self):
        """Initialize resource monitor."""
        self._start_time: Optional[float] = None
        self._memory_samples: list[float] = []
        self._api_calls = 0
        self._data_points = 0
        self._trades = 0
        self._process = psutil.Process() if PSUTIL_AVAILABLE else None

    def start(self) -> None:
        """Start monitoring."""
        self._start_time = time.time()
        self._memory_samples = []
        self._api_calls = 0
        self._data_points = 0
        self._trades = 0

        if self._process:
            self._sample_memory()

        logger.debug("Resource monitoring started")

    def stop(self) -> ResourceUsage:
        """
        Stop monitoring and return usage.

        Returns:
            ResourceUsage with collected metrics
        """
        if self._start_time is None:
            return ResourceUsage()

        execution_time = time.time() - self._start_time

        # Final memory sample
        if self._process:
            self._sample_memory()

        peak_memory = max(self._memory_samples) if self._memory_samples else 0
        avg_memory = (
            sum(self._memory_samples) / len(self._memory_samples)
            if self._memory_samples else 0
        )

        # Calculate estimated costs
        compute_cost = (execution_time / 3600) * self.COMPUTE_COST_PER_HOUR_USD
        api_cost = self._api_calls * self.API_COST_PER_CALL_USD
        storage_cost = (peak_memory / 1024) * self.STORAGE_COST_PER_MB_USD  # GB

        usage = ResourceUsage(
            execution_time_seconds=execution_time,
            peak_memory_mb=peak_memory,
            avg_memory_mb=avg_memory,
            api_calls=self._api_calls,
            data_points_processed=self._data_points,
            trades_executed=self._trades,
            estimated_compute_cost_usd=compute_cost,
            estimated_api_cost_usd=api_cost,
            estimated_storage_cost_usd=storage_cost,
        )

        logger.debug(f"Resource monitoring stopped: {usage.to_dict()}")

        return usage

    def _sample_memory(self) -> None:
        """Take a memory sample."""
        if self._process:
            try:
                memory_info = self._process.memory_info()
                memory_mb = memory_info.rss / (1024 * 1024)
                self._memory_samples.append(memory_mb)
            except Exception:
                pass

    def record_api_call(self, count: int = 1) -> None:
        """Record API call(s)."""
        self._api_calls += count
        self._sample_memory()

    def record_data_points(self, count: int) -> None:
        """Record data points processed."""
        self._data_points += count

    def record_trade(self, count: int = 1) -> None:
        """Record trade(s) executed."""
        self._trades += count

    def get_current_memory_mb(self) -> float:
        """Get current memory usage in MB."""
        if self._process:
            try:
                return self._process.memory_info().rss / (1024 * 1024)
            except Exception:
                return 0.0
        return 0.0

    def get_elapsed_seconds(self) -> float:
        """Get elapsed time since start."""
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time
