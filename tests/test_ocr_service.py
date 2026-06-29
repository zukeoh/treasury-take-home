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
from app.ocr_service import (
    EasyOcrProvider,
    OcrService,
    TesseractOcrProvider,
    create_ocr_provider,
    parse_tesseract_data,
    prepare_tesseract_image,
)
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

    provider = EasyOcrProvider()
    provider._reader = FakeReader()
    service = OcrService(provider)
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
    provider = EasyOcrProvider()
    provider._reader = LowConfidenceReader()
    service = OcrService(provider)

    result = service.extract(prepared)

    assert config.OCR_MAX_WORKERS == 2
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
    assert "tesseract-ocr" in dockerfile
    assert "/healthz" in dockerfile
    assert "secret" not in render_config.casefold()
    assert "healthCheckPath: /healthz" in render_config
    assert "key: OCR_ENGINE\n        value: tesseract" in render_config
    assert 'key: OCR_MAX_WORKERS\n        value: "1"' in render_config
    assert 'key: MAX_OCR_IMAGE_DIMENSION\n        value: "1600"' in render_config
    assert 'key: ENABLE_SECOND_OCR_PASS\n        value: "false"' in render_config
    assert 'key: TESSERACT_PSM\n        value: "11"' in render_config
    assert 'key: TESSERACT_DESKEW\n        value: "true"' in render_config


def test_ocr_engine_defaults_to_easyocr() -> None:
    assert config.OCR_ENGINE == "easyocr"
    assert isinstance(create_ocr_provider(), EasyOcrProvider)


def test_tesseract_engine_selects_tesseract_provider() -> None:
    assert isinstance(create_ocr_provider("tesseract"), TesseractOcrProvider)


def test_easyocr_engine_selects_easyocr_provider() -> None:
    assert isinstance(create_ocr_provider("easyocr"), EasyOcrProvider)


def test_invalid_ocr_engine_falls_back_safely(caplog) -> None:
    caplog.set_level("WARNING", logger="app.ocr_service")

    provider = create_ocr_provider("not-an-engine")

    assert isinstance(provider, EasyOcrProvider)
    assert "falling back to easyocr" in caplog.text


def test_tesseract_confidence_parsing_ignores_negative_values() -> None:
    data = {
        "text": ["ignored", "Hello", "World"],
        "conf": ["-1", "90", "80"],
        "page_num": [1, 1, 1],
        "block_num": [1, 1, 1],
        "par_num": [1, 1, 1],
        "line_num": [1, 1, 1],
        "left": [0, 10, 60],
        "top": [0, 20, 20],
        "width": [5, 40, 50],
        "height": [5, 10, 10],
    }

    result = parse_tesseract_data(data, elapsed_ms=123)

    assert result.engine == "tesseract"
    assert result.elapsed_ms == 123
    assert result.text == "Hello World"
    assert len(result.blocks) == 1
    assert result.blocks[0].confidence == 0.85
    assert result.blocks[0].bbox == [10.0, 20.0, 100.0, 10.0]
    assert result.average_confidence == 0.85


def test_tesseract_uses_label_preprocessing_and_sparse_text_mode() -> None:
    captured: dict[str, object] = {}

    class FakePytesseract:
        class Output:
            DICT = "dict"

        def image_to_data(self, image, **kwargs):
            captured["shape"] = image.shape
            captured.update(kwargs)
            return {"text": [], "conf": []}

    provider = TesseractOcrProvider()
    provider._pytesseract = FakePytesseract()
    result = provider.read(np.full((120, 240, 3), 255, dtype=np.uint8))

    assert config.TESSERACT_PSM == 11
    assert config.TESSERACT_DESKEW is True
    assert captured["shape"] == (144, 264)
    assert captured["lang"] == "eng"
    assert captured["config"] == "--oem 1 --psm 11"
    assert result.engine == "tesseract"


def test_tesseract_preprocessing_preserves_a_bounded_image() -> None:
    image = np.full((80, 160, 3), 255, dtype=np.uint8)
    prepared, angle = prepare_tesseract_image(image)

    assert prepared.dtype == np.uint8
    assert prepared.shape == (104, 184)
    assert angle == 0.0


def test_tesseract_preprocessing_inverts_uniformly_dark_artwork() -> None:
    image = np.full((100, 180, 3), 17, dtype=np.uint8)
    image[35:65, 45:135] = 65

    prepared, _ = prepare_tesseract_image(image)

    interior = prepared[12:-12, 12:-12]
    assert float(np.median(interior)) > 200


def test_tesseract_preprocessing_binarizes_dark_glare_artwork() -> None:
    image = np.full((100, 180, 3), 35, dtype=np.uint8)
    image[:, 105:145] = 180

    prepared, _ = prepare_tesseract_image(image)

    assert set(np.unique(prepared)).issubset({0, 255})
