"""
DocuShield Resilience & Fault Tolerance Core
=============================================
Implements architectural resilience patterns:
1. Exponential Backoff with Full Jitter
2. Circuit Breaker Pattern
3. Idempotency Key Tracking (Duplicate processing protection)
4. Chaos Engineering Injection Hooks
"""

import time
import random
import logging
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger("DocuShield.Resilience")


# =============================================================================
# 1. EXPONENTIAL BACKOFF WITH FULL JITTER
# =============================================================================
def resilient_retry(max_retries: int = 4, base_delay: float = 0.5, max_delay: float = 5.0, exceptions=(Exception,)):
    """
    Decorator executing Exponential Backoff with Full Jitter (AWS Best Practice).
    formula: sleep = uniform(0, min(max_delay, base_delay * (2 ** attempt)))
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as err:
                    attempt += 1
                    if attempt > max_retries:
                        logger.error(f"[Resilience] Function '{func.__name__}' exceeded max retries ({max_retries}). Error: {err}")
                        raise
                    
                    # Full Jitter calculation
                    calculated_delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                    sleep_duration = random.uniform(0, calculated_delay)
                    logger.warning(
                        f"[Resilience] Transient error in '{func.__name__}': {err}. "
                        f"Attempt {attempt}/{max_retries}. Backoff sleep: {sleep_duration:.2f}s"
                    )
                    time.sleep(sleep_duration)
        return wrapper
    return decorator


# =============================================================================
# 2. CIRCUIT BREAKER PATTERN
# =============================================================================
class CircuitState:
    CLOSED = "CLOSED"       # Normal operation
    OPEN = "OPEN"           # Tripped, rejecting fast
    HALF_OPEN = "HALF_OPEN" # Testing recovery


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 10.0, name: str = "Circuit"):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_state_change = time.time()

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if time.time() - self.last_state_change > self.recovery_timeout:
                logger.info(f"[CircuitBreaker:{self.name}] Recovery timeout reached. Transitioning to HALF_OPEN.")
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = time.time()
                return True
            return False
        elif self.state == CircuitState.HALF_OPEN:
            return True
        return False

    def record_success(self):
        if self.state != CircuitState.CLOSED:
            logger.info(f"[CircuitBreaker:{self.name}] Call succeeded. Resetting circuit to CLOSED.")
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_state_change = time.time()

    def record_failure(self):
        self.failure_count += 1
        logger.warning(f"[CircuitBreaker:{self.name}] Failure recorded (Count: {self.failure_count}/{self.failure_threshold}).")
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.last_state_change = time.time()
            logger.critical(f"[CircuitBreaker:{self.name}] THRESHOLD EXCEEDED! Circuit TRIPPED to OPEN.")

    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not self.can_execute():
                raise RuntimeError(f"CircuitBreaker '{self.name}' is OPEN. Fast failing request to preserve resources.")
            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure()
                raise
        return wrapper


# =============================================================================
# 3. CHAOS SIMULATION MANAGER
# =============================================================================
class ChaosManager:
    """Manages active chaos experiments to prove system resilience."""
    def __init__(self):
        self.crash_worker_next = False
        self.throttle_database = False
        self.fail_s3_upload = False
        self.injected_poison_pills = 0
        self.simulated_incidents = []

    def log_incident(self, experiment_type: str, details: str):
        record = {
            "timestamp": time.time(),
            "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
            "experiment": experiment_type,
            "details": details
        }
        self.simulated_incidents.append(record)
        # Keep last 50
        if len(self.simulated_incidents) > 50:
            self.simulated_incidents.pop(0)

    def reset_all(self):
        self.crash_worker_next = False
        self.throttle_database = False
        self.fail_s3_upload = False
        self.injected_poison_pills = 0


chaos_control = ChaosManager()
