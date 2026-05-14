"""Apache Kafka producer + consumer helpers (aiokafka).

Patterns:
  - Pub/Sub (Kafka topics + consumer groups)
  - Outbox-lite (publish + db-write live in same async block in main.py)
  - Circuit breaker stub (TODO: student completes)

Partition keying:
  Every saga-critical publish should pass key=<incident_id> (or <user_id>).
  Same-key events land on the same partition, preserving ordering and ensuring
  the "no double dispatch" invariant holds even with multi-replica consumers
  (one partition is owned by one consumer at a time inside a group).
"""
from __future__ import annotations
import json
import os
from typing import Awaitable, Callable, Iterable

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")

_producer: AIOKafkaProducer | None = None


async def producer() -> AIOKafkaProducer:
    global _producer
    if _producer is None:
        _producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            enable_idempotence=True,
            acks="all",
            value_serializer=lambda v: json.dumps(v).encode(),
            key_serializer=lambda k: k.encode() if k else None,
        )
        await _producer.start()
    return _producer


async def stop_producer() -> None:
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None


async def health() -> bool:
    """Liveness ping for /readyz — verify broker reachable + metadata fetch works."""
    try:
        p = await producer()
        await p.client.fetch_all_metadata()
        return True
    except Exception:
        return False


# ---- Circuit breaker: open/half-open/closed state machine ----
import time
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(self, fail_threshold: int = 5, reset_after_s: float = 10.0):
        self.fail_threshold = fail_threshold
        self.reset_after_s = reset_after_s
        self.fails = 0
        self.opened_at: float | None = None
        self.state = CircuitState.CLOSED
        self.half_open_attempt = False

    def allow(self) -> bool:
        """Check if request is allowed based on circuit state."""
        now = time.time()
        
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if enough time has passed to try recovery
            if self.opened_at is not None and now - self.opened_at >= self.reset_after_s:
                self.state = CircuitState.HALF_OPEN
                self.half_open_attempt = False
                return True
            return False
        
        # HALF_OPEN: allow one attempt
        if self.state == CircuitState.HALF_OPEN and not self.half_open_attempt:
            self.half_open_attempt = True
            return True
        
        return False

    def record_success(self) -> None:
        """Record a successful call; reset state."""
        self.fails = 0
        if self.state == CircuitState.HALF_OPEN:
            # Recovery successful; return to CLOSED
            self.state = CircuitState.CLOSED
            self.opened_at = None

    def record_failure(self) -> None:
        """Record a failed call; possibly open the circuit."""
        self.fails += 1
        if self.state == CircuitState.HALF_OPEN:
            # Recovery attempt failed; reopen
            self.state = CircuitState.OPEN
            self.opened_at = time.time()
        elif self.state == CircuitState.CLOSED and self.fails >= self.fail_threshold:
            # Threshold reached; open the circuit
            self.state = CircuitState.OPEN
            self.opened_at = time.time()


_breaker = CircuitBreaker()


async def publish(topic: str, event: dict, key: str | None = None) -> None:
    """Outbox-lite: caller should db-write THEN await publish() in same async block."""
    if not _breaker.allow():
        raise RuntimeError(f"circuit-open: {topic}")
    try:
        p = await producer()
        await p.send_and_wait(topic, value=event, key=key)
        _breaker.record_success()
    except Exception:
        _breaker.record_failure()
        raise


Handler = Callable[[dict], Awaitable[None]]


async def consume(topics: Iterable[str], group: str, handler: Handler) -> None:
    """Consumer-group reader. Manual commit only on successful handler (at-least-once)."""
    consumer = AIOKafkaConsumer(
        *topics,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=group,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode()),
    )
    await consumer.start()
    try:
        async for msg in consumer:
            payload = msg.value
            payload["_stream"] = msg.topic  # preserved name for back-compat with handlers
            try:
                await handler(payload)
                await consumer.commit()
            except Exception:
                # leave un-committed → re-delivered on next read (at-least-once)
                pass
    finally:
        await consumer.stop()
