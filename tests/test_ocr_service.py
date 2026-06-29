from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from app.image_service import PreparedImage
from app.ocr_service import OcrService


def test_process_wide_gate_serializes_easyocr_by_default() -> None:
    lock = threading.Lock()
    active = 0
    peak = 0

    class FakeReader:
        def readtext(self, image, **kwargs):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                time.sleep(0.02)
                return [(None, "readable label text", 0.95)]
            finally:
                with lock:
                    active -= 1

    service = OcrService()
    service._reader = FakeReader()
    pixels = np.zeros((10, 10, 3), dtype=np.uint8)
    image = PreparedImage(original=pixels, enhanced=pixels, width=10, height=10)

    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(service.extract, [image, image, image]))

    assert all(result.text == "readable label text" for result in results)
    assert peak == 1


def test_deployment_uses_one_uvicorn_worker_without_render_secrets() -> None:
    root = Path(__file__).parents[1]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    render_config = (root / "render.yaml").read_text(encoding="utf-8")

    assert "--workers 1" in dockerfile
    assert "PYTHONUNBUFFERED=1" in dockerfile
    assert "/healthz" in dockerfile
    assert "envVars:" not in render_config
    assert "secret" not in render_config.casefold()
    assert "healthCheckPath: /healthz" in render_config
