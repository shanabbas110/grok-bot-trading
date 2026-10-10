"""In-process decision counters for paper sessions and summaries."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from threading import Lock


@dataclass
class ModelStats:
    calls: int = 0
    errors: int = 0
    latency_ms_total: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        return self.latency_ms_total / self.calls if self.calls else 0.0


class DecisionMetrics:
    _lock = Lock()
    _stats: dict[str, ModelStats] = defaultdict(ModelStats)
    _session_errors: list[str] = []

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._stats = {}
            cls._session_errors = []

    @classmethod
    def record(cls, model: str, latency_ms: float, error: str | None = None) -> None:
        with cls._lock:
            st = cls._stats.setdefault(model, ModelStats())
            st.calls += 1
            st.latency_ms_total += latency_ms
            if error:
                st.errors += 1
                cls._session_errors.append(f"{model}: {error}")

    @classmethod
    def summary(cls) -> dict:
        with cls._lock:
            models = {
                name: {
                    "calls": st.calls,
                    "errors": st.errors,
                    "avg_latency_ms": round(st.avg_latency_ms, 1),
                }
                for name, st in cls._stats.items()
            }
            return {"models": models, "errors": list(cls._session_errors)}
