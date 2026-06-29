"""Request-scoped structured logging and process memory diagnostics."""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

import psutil

from app import config


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT,
)

logger = logging.getLogger("app.verification")
logger.setLevel(config.LOG_LEVEL)
process = psutil.Process(os.getpid())


def current_rss_mb() -> float | None:
    try:
        return process.memory_info().rss / (1024 * 1024)
    except (psutil.Error, OSError):
        return None


class RequestTrace:
    """Keep one request ID, timings, and peak observed RSS across worker threads."""

    def __init__(self) -> None:
        self.request_id = uuid4().hex[:8]
        self.start_time = time.perf_counter()
        self.peak_rss_mb = 0.0
        self._lock = threading.Lock()

    def current_rss_mb(self) -> float | None:
        rss_mb = current_rss_mb()
        if rss_mb is not None:
            with self._lock:
                self.peak_rss_mb = max(self.peak_rss_mb, rss_mb)
        return rss_mb

    def peak_memory_mb(self) -> float:
        with self._lock:
            return self.peak_rss_mb

    def info(self, message: str, *args: object) -> None:
        logger.info("[%s] " + message, self.request_id, *args)

    def exception(self, message: str, *args: object) -> None:
        logger.exception("[%s] " + message, self.request_id, *args)

    def stage(self, number: int, name: str, image_context: str = "") -> None:
        suffix = f" | {image_context}" if image_context else ""
        self.info("STEP %d %s%s", number, name, suffix)

    def mark(self, stage_name: str, image_context: str = "") -> float | None:
        suffix = f" | {image_context}" if image_context else ""
        self.info("MARK %s%s", stage_name, suffix)
        return self.memory(stage_name, image_context)

    def memory(self, stage: str, image_context: str = "") -> float | None:
        rss_mb = self.current_rss_mb()
        if rss_mb is not None:
            suffix = f" | {image_context}" if image_context else ""
            self.info("%s | Memory: %.1f MB%s", stage, rss_mb, suffix)
        else:
            suffix = f" | {image_context}" if image_context else ""
            self.info("%s | Memory: unavailable%s", stage, suffix)
        return rss_mb

    @contextmanager
    def time_block(self, stage_name: str, image_context: str = "") -> Iterator[None]:
        started_at = time.perf_counter()
        self.info("Timing start | %s | %s", stage_name, image_context)
        try:
            yield
        except Exception:
            self.exception("%s failed | %s", stage_name, image_context)
            raise
        finally:
            self.timing(stage_name, started_at, image_context)

    def timing(self, stage: str, started_at: float, image_context: str = "") -> float:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        suffix = f" | {image_context}" if image_context else ""
        self.info("%s: %.0f ms%s", stage, elapsed_ms, suffix)
        return elapsed_ms

    def request_start(self, image_count: int, csv_uploaded: bool) -> None:
        self.info("==============================")
        self.info("Starting verification request")
        self.info("Request ID: %s", self.request_id)
        self.info("Images uploaded: %d", image_count)
        self.info("CSV uploaded: %s", str(csv_uploaded).lower())
        self.info("==============================")
        self.memory("Request start")

    def log_summary(self, images_processed: int) -> None:
        final_rss = self.memory("End request")
        elapsed = time.perf_counter() - self.start_time
        self.info("========================================")
        self.info("Verification complete")
        self.info("Request ID: %s", self.request_id)
        self.info("Images processed: %d", images_processed)
        self.info("Overall elapsed: %.1f sec", elapsed)
        self.info("Peak memory observed: %.1f MB", self.peak_memory_mb())
        if final_rss is None:
            self.info("Final memory: unavailable")
        else:
            self.info("Final memory: %.1f MB", final_rss)
        self.info("========================================")

    def request_summary(self, images_processed: int) -> None:
        """Backward-compatible alias for callers while logs use log_summary()."""

        self.log_summary(images_processed)
