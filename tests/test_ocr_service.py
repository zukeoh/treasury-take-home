from __future__ import annotations

import io
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

from app import config
from app.image_service import PreparedImage, prepare_image
from app.ocr_service import OcrService
from app.telemetry import LOG_FORMAT, RequestTrace


def test_process_wide_gate_serializes_easyocr_by_default(caplog) -> None:
    caplog.set_level("INFO", logger="app.ocr_service")
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
    trace = RequestTrace()
    assert LOG_FORMAT == "%(asctime)s %(levelname)s %(name)s %(message)s"
    assert len(trace.request_id) == 8
    assert trace.start_time > 0
    assert trace.current_rss_mb() is not None
    assert trace.peak_rss_mb > 0
    assert callable(trace.mark)
    assert callable(trace.time_block)
    assert callable(trace.log_summary)
    pixels = np.zeros((10, 10, 3), dtype=np.uint8)
    image = PreparedImage(original=pixels, enhanced=pixels, width=10, height=10)

    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(
            executor.map(
                lambda value: service.extract(value, trace, "test-image"),
                [image, image, image],
            )
        )

    assert all(result.text == "readable label text" for result in results)
    assert peak == 1
    assert "MARK before_ocr" in caplog.text
    assert "MARK after_ocr" in caplog.text


def test_second_pass_and_enhanced_buffer_are_disabled_by_default() -> None:
    calls = 0

    class LowConfidenceReader:
        def readtext(self, image, **kwargs):
            nonlocal calls
            calls += 1
            return [(None, "uncertain text", 0.2)]

    source = io.BytesIO()
    Image.new("RGB", (2000, 1000), "white").save(source, format="PNG")
    prepared = prepare_image(source.getvalue(), "large-label.png", "image/png")
    service = OcrService()
    service._reader = LowConfidenceReader()

    result = service.extract(prepared)

    assert config.OCR_MAX_WORKERS == 1
    assert config.MAX_OCR_IMAGE_DIMENSION == 1600
    assert config.ENABLE_SECOND_OCR_PASS is False
    assert max(prepared.width, prepared.height) == 1600
    assert prepared.original.shape[2] == 3
    assert prepared.enhanced is None
    assert result.used_enhanced_pass is False
    assert calls == 1


def test_deployment_uses_conservative_ocr_defaults_without_render_secrets() -> None:
    root = Path(__file__).parents[1]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    render_config = (root / "render.yaml").read_text(encoding="utf-8")

    assert "--workers 1" in dockerfile
    assert "PYTHONUNBUFFERED=1" in dockerfile
    assert "/healthz" in dockerfile
    assert "secret" not in render_config.casefold()
    assert "healthCheckPath: /healthz" in render_config
    assert 'key: OCR_MAX_WORKERS\n        value: "1"' in render_config
    assert 'key: MAX_OCR_IMAGE_DIMENSION\n        value: "1600"' in render_config
    assert 'key: ENABLE_SECOND_OCR_PASS\n        value: "false"' in render_config
