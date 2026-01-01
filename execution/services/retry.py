"""
Retry service with exponential backoff.

Extracted from AlpacaBroker for reuse across all API calls.
"""
import logging
import time
from dataclasses import dataclass
from typing import TypeVar, Callable, Optional, Set

logger = logging.getLogger(__name__)

T = TypeVar("T")


# Retryable HTTP status codes
RETRYABLE_STATUS_CODES: Set[int] = {
    408,  # Request Timeout
    429,  # Too Many Requests (Rate Limit)
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
}

# Error messages that indicate retryable failures
RETRYABLE_ERROR_PATTERNS = [
    "timeout",
    "timed out",
    "connection reset",
    "connection refused",
    "connection aborted",
    "temporary failure",
    "service unavailable",
    "rate limit",
    "too many requests",
    "network unreachable",
    "name resolution",
]


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 30.0  # seconds
    exponential_base: float = 2.0

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay before next retry using exponential backoff.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = self.base_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)


class RetryService:
    """
    Generic retry service with exponential backoff.

    Can be used for any operation that may fail transiently.
    """

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()

    def is_retryable_error(self, error: Exception) -> bool:
        """
        Check if an error is retryable.

        Args:
            error: The exception to check

        Returns:
            True if the error is retryable
        """
        error_str = str(error).lower()

        # Check for retryable patterns in error message
        for pattern in RETRYABLE_ERROR_PATTERNS:
            if pattern in error_str:
                return True

        # Check for status code in error
        if hasattr(error, "status_code"):
            if error.status_code in RETRYABLE_STATUS_CODES:
                return True

        # Check for common network exception types
        error_type = type(error).__name__.lower()
        if any(t in error_type for t in ["timeout", "connection", "network"]):
            return True

        return False

    def execute_with_retry(
        self,
        operation: Callable[[], T],
        operation_name: str = "operation",
        on_retry: Optional[Callable[[Exception, int], None]] = None,
        on_failure: Optional[Callable[[Exception], T]] = None,
    ) -> T:
        """
        Execute an operation with retry logic.

        Args:
            operation: Callable to execute
            operation_name: Name for logging purposes
            on_retry: Callback called on each retry (error, attempt)
            on_failure: Callback called on final failure, can return fallback

        Returns:
            Result of operation

        Raises:
            Exception: The last exception if all retries fail and no on_failure handler
        """
        last_error: Optional[Exception] = None

        for attempt in range(self.config.max_retries + 1):
            try:
                return operation()

            except Exception as e:
                last_error = e

                if not self.is_retryable_error(e):
                    logger.error(f"Non-retryable error in {operation_name}: {e}")
                    if on_failure:
                        return on_failure(e)
                    raise

                if attempt < self.config.max_retries:
                    delay = self.config.calculate_delay(attempt)
                    logger.warning(
                        f"{operation_name} failed (attempt {attempt + 1}/{self.config.max_retries + 1}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    if on_retry:
                        on_retry(e, attempt)

                    time.sleep(delay)

        # All retries exhausted
        logger.error(
            f"{operation_name} failed after {self.config.max_retries + 1} attempts: {last_error}"
        )

        if on_failure and last_error:
            return on_failure(last_error)

        if last_error:
            raise last_error

        raise RuntimeError(f"{operation_name} failed with unknown error")

    async def execute_with_retry_async(
        self,
        operation: Callable[[], T],
        operation_name: str = "operation",
    ) -> T:
        """
        Async version of execute_with_retry.

        Note: Uses asyncio.sleep instead of time.sleep
        """
        import asyncio

        last_error: Optional[Exception] = None

        for attempt in range(self.config.max_retries + 1):
            try:
                result = operation()
                if asyncio.iscoroutine(result):
                    return await result
                return result

            except Exception as e:
                last_error = e

                if not self.is_retryable_error(e):
                    logger.error(f"Non-retryable error in {operation_name}: {e}")
                    raise

                if attempt < self.config.max_retries:
                    delay = self.config.calculate_delay(attempt)
                    logger.warning(
                        f"{operation_name} failed (attempt {attempt + 1}/{self.config.max_retries + 1}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)

        if last_error:
            raise last_error

        raise RuntimeError(f"{operation_name} failed with unknown error")
