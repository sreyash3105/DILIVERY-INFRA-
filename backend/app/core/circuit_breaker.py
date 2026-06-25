import time
import logging
import threading
from typing import Callable, Any, Optional

logger = logging.getLogger("CircuitBreaker")

class CircuitBreakerOpenException(Exception):
    """Raised when a request is blocked because the circuit is OPEN."""
    pass

class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_trials: int = 3
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_trials = half_open_trials
        
        self.state = "CLOSED"
        self.failures = 0
        self.successful_trials = 0
        self.last_state_change = time.time()
        self.lock = threading.Lock()

    def __call__(self, func: Callable[..., Any], fallback: Callable[..., Any]) -> Callable[..., Any]:
        """Decorates or wraps synchronous/asynchronous calls with the circuit breaker."""
        import asyncio
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                return await self.call_async(func, fallback, *args, **kwargs)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                return self.call_sync(func, fallback, *args, **kwargs)
            return sync_wrapper

    def _before_call(self):
        with self.lock:
            now = time.time()
            if self.state == "OPEN":
                # Check if cooling down time has elapsed
                if now - self.last_state_change > self.recovery_timeout:
                    logger.warning(f"Circuit Breaker [{self.name}] transitioning to HALF-OPEN for trials.")
                    self.state = "HALF-OPEN"
                    self.successful_trials = 0
                    self.last_state_change = now
                else:
                    raise CircuitBreakerOpenException(f"Circuit [{self.name}] is open. Request blocked.")

    def _on_success(self):
        with self.lock:
            if self.state == "HALF-OPEN":
                self.successful_trials += 1
                if self.successful_trials >= self.half_open_trials:
                    logger.info(f"Circuit Breaker [{self.name}] successfully recovered and is CLOSED.")
                    self.state = "CLOSED"
                    self.failures = 0
                    self.last_state_change = time.time()
            elif self.state == "CLOSED":
                self.failures = 0

    def _on_failure(self):
        with self.lock:
            self.failures += 1
            now = time.time()
            logger.warning(f"Circuit Breaker [{self.name}] recorded failure #{self.failures} in state {self.state}")
            if self.state in ("CLOSED", "HALF-OPEN") and self.failures >= self.failure_threshold:
                logger.error(f"Circuit Breaker [{self.name}] threshold exceeded! Tripping to OPEN for {self.recovery_timeout}s.")
                self.state = "OPEN"
                self.last_state_change = now

    def call_sync(self, func: Callable[..., Any], fallback: Callable[..., Any], *args, **kwargs) -> Any:
        try:
            self._before_call()
        except CircuitBreakerOpenException:
            return fallback(*args, **kwargs)

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            return fallback(*args, **kwargs)

    async def call_async(self, func: Callable[..., Any], fallback: Callable[..., Any], *args, **kwargs) -> Any:
        try:
            self._before_call()
        except CircuitBreakerOpenException:
            # Execute fallback
            if asyncio.iscoroutinefunction(fallback):
                return await fallback(*args, **kwargs)
            return fallback(*args, **kwargs)

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            if asyncio.iscoroutinefunction(fallback):
                return await fallback(*args, **kwargs)
            return fallback(*args, **kwargs)
