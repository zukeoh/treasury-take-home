from __future__ import annotations

import base64
import io
import json
import re
import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.config import GOVERNMENT_WARNING
from app.main import app
from app.models import OcrFragment, OcrResult
from app.ocr_service import ocr_service


def _png() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (800, 1000), "white").save(output, format="PNG")
    return output.getvalue()


def test_home_page_loads() -> None:
    with TestClient(app) as client:
        response = client.get("/")
        stylesheet = client.get("/static/styles.css")
        application_script = client.get("/static/app.js")
    assert response.status_code == 200
    assert stylesheet.status_code == 200
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert application_script.status_code == 200
    assert 'href="/static/vendor/bootstrap.min.css"' in response.text
    assert 'href="/static/styles.css"' in response.text
    assert 'src="/static/theme.js"' in response.text
    assert 'src="/static/app.js"' in response.text
    assert "://testserver/static/" not in response.text
    assert "Start A Label Review" in response.text
    assert "An official prototype for label compliance review" not in response.text
    assert "Compliance review workspace" not in response.text
    assert "Ready for a first-pass check" not in response.text
    assert "Results include a field-by-field explanation" not in response.text
    assert 'data-field="imported"' in response.text
    assert 'data-field="country_of_origin"' in response.text
    assert "disabled" in response.text
    assert "Beer / malt beverage" in response.text
    assert "Wine Fields" in response.text
    assert "Distilled Spirits Fields" in response.text
    assert 'id="image-list"' in response.text
    assert 'id="image-item-template"' in response.text
    assert "data-remove-file" in response.text
    assert "data-application-thumbnail" in response.text
    assert 'data-max-images="300"' in response.text
    assert 'id="review-loading-template"' in response.text
    assert "Reading and Verifying Labels" in response.text
    assert "data-loading-estimate" in response.text
    assert "data-loading-elapsed" in response.text
    assert 'id="theme-toggle"' in response.text
    assert "/static/theme.js" in response.text
    assert "ttb-color-theme" in response.text
    assert 'id="application-data-step" aria-disabled="true" inert' in response.text
    assert "Add at least one label image above to continue." in response.text
    assert "Add label images first. One application section will appear" in response.text
    assert "What gets checked" not in response.text
    assert "Decision support only" not in response.text
    assert "Uploads are processed in memory" not in response.text
    assert "Official TTB references" in response.text
    assert "https://www.ttb.gov/regulated-commodities/beverage-alcohol/beer/labeling" in response.text
    assert "https://www.ttb.gov/regulated-commodities/beverage-alcohol/wine/labeling" in response.text


def test_healthz_reports_application_status() -> None:
    with TestClient(app) as client:
        response = client.get("/healthz")
        old_route = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] in {"ok", "degraded"}
    assert "ocr_ready" in response.json()
    assert old_route.status_code == 404


def test_upload_script_retains_and_removes_individual_files() -> None:
    script = (Path(__file__).parents[1] / "app" / "static" / "app.js").read_text()
    styles = (Path(__file__).parents[1] / "app" / "static" / "styles.css").read_text()
    assert "new DataTransfer()" in script
    assert "selectedFiles.push(file)" in script
    assert "selectedFiles.splice(index, 1)" in script
    assert "highlightDuplicates(duplicateKeys)" in script
    assert 'card.classList.add("is-duplicate")' in script
    assert "refreshSelectedFiles()" in script
    assert ".image-item.is-duplicate" in styles
    assert "@keyframes duplicate-shake" in styles
    assert "applicationDataStep.inert = applicationLocked" in script
    assert ".application-data-step.is-locked" in styles
    assert 'window.history.pushState({ navigationBase: "processing" }, "", "/verify")' in script
    assert 'window.history.pushState(processingGuardState, "", "/verify")' in script
    assert 'fetch("/verify", { method: "POST", body: submission })' in script
    assert "Math.ceil(labelCount * 3.5)" in script
    assert "updateEstimatedProgress" in script
    assert "Label verification is still processing" in script
    assert 'window.addEventListener("popstate", guardProcessingHistory)' in script
    assert 'window.addEventListener("beforeunload", guardProcessingUnload)' in script


def test_sample_csv_uses_plain_language_columns() -> None:
    with TestClient(app) as client:
        response = client.get("/sample.csv")
    assert response.status_code == 200
    assert response.text.startswith(
        "file_name,beverage_type,brand_name,product_type,abv,net_contents,producer"
    )


def test_no_image_has_friendly_error() -> None:
    with TestClient(app) as client:
        response = client.post("/verify", data={})
    assert response.status_code == 400
    assert "Choose at least one JPEG or PNG" in response.text


def test_imported_manual_submission_requires_country() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/verify",
            files={"images": ("label.png", _png(), "image/png")},
            data={
                "manual_applications": json.dumps([
                    {
                        "file_name": "label.png",
                        "beverage_type": "distilled_spirits",
                        "brand_name": "TEST",
                        "class_type": "Whiskey",
                        "alcohol_content": "40% ABV",
                        "net_contents": "750 mL",
                        "bottler_name_address": "Test Producer",
                        "imported": True,
                    }
                ])
            },
        )
    assert response.status_code == 400
    assert "country of origin" in response.text


def test_complete_manual_submission_renders_pass(monkeypatch) -> None:
    lines = [
        "OLD TOM DISTILLERY",
        "Kentucky Straight Bourbon Whiskey",
        "45% Alc./Vol. (90 Proof)",
        "750 mL",
        "Old Tom Distillery, Louisville, KY",
        GOVERNMENT_WARNING,
    ]
    fake_ocr = OcrResult(
        fragments=[OcrFragment(text=line, confidence=0.96) for line in lines],
        text="\n".join(lines),
        average_confidence=0.96,
    )
    monkeypatch.setattr(ocr_service, "extract", lambda image: fake_ocr)

    with TestClient(app) as client:
        response = client.post(
            "/verify",
            files={"images": ("old_tom.png", _png(), "image/png")},
            data={
                "manual_applications": json.dumps([
                    {
                        "file_name": "old_tom.png",
                        "beverage_type": "distilled_spirits",
                        "brand_name": "OLD TOM DISTILLERY",
                        "class_type": "Kentucky Straight Bourbon Whiskey",
                        "alcohol_content": "45% Alc./Vol. (90 Proof)",
                        "net_contents": "750 mL",
                        "bottler_name_address": "Old Tom Distillery, Louisville, KY",
                    }
                ])
            },
        )
    assert response.status_code == 200
    assert "old_tom.png" in response.text
    assert "status-pass" in response.text
    assert "Warning Typography &amp; Physical Size" in response.text
    assert "Physical font size cannot be determined without scale metadata" in response.text
    assert "Requirement &amp; Source" in response.text
    assert "Common required warning for alcohol beverages" in response.text
    assert "TTB Distilled Spirits Health Warning" in response.text
    assert 'id="export-results"' in response.text
    assert 'id="start-another-review"' in response.text
    assert 'data-result-filter="PASS"' in response.text
    assert 'data-result-filter="FAIL"' in response.text
    assert 'data-result-filter="NEEDS REVIEW"' in response.text
    assert 'data-result-filter="overwritten"' in response.text
    assert "data-count-overwritten" in response.text
    assert 'data-result-status="PASS"' in response.text
    assert "data-result-position" in response.text
    assert "Result 1 Of 1" in response.text
    assert 'class="result-thumbnail" src="data:image/jpeg;base64,' in response.text
    assert 'id="image-viewer"' in response.text
    assert "data-image-open" in response.text
    assert 'id="image-viewer-close"' in response.text
    assert 'id="export-data"' in response.text
    assert "OLD TOM DISTILLERY" in response.text
    assert "Upload another label" not in response.text
    assert "results-references-title" not in response.text
    assert '<section class="footer-reference-group">' in response.text
    assert "Labeling Requirements" in response.text
    assert "Health Warning" in response.text
    assert 'id="toggle-all-results"' in response.text
    assert "data-result-toggle" in response.text
    assert "data-result-details" in response.text
    assert 'id="scroll-to-top"' in response.text
    assert "All automated required checks passed" in response.text
    assert "Human agents make the final determination" in response.text
    assert "Field-level findings remain unchanged" in response.text
    assert response.text.index("How To Use These Results") < response.text.index('class="summary-strip"')
    assert response.text.count("data-override-status=") == 3
    export_match = re.search(
        r'<script id="export-data" type="application/json">(.*?)</script>',
        response.text,
        re.DOTALL,
    )
    assert export_match is not None
    export_payload = json.loads(export_match.group(1))
    assert export_payload["rows"][0]["file_name"] == "old_tom.png"
    assert export_payload["rows"][0]["brand_name"] == "OLD TOM DISTILLERY"
    assert export_payload["rows"][0]["original_result"] == "PASS"
    assert export_payload["rows"][0]["final_result"] == "PASS"
    assert export_payload["rows"][0]["overwritten"] is False
    assert 'data-original-status="PASS"' in response.text
    assert 'data-override-status="PASS"' in response.text
    assert 'data-override-status="NEEDS REVIEW"' in response.text
    assert 'data-override-status="FAIL"' in response.text
    preview_match = re.search(
        r'class="result-thumbnail" src="data:image/jpeg;base64,([^"]+)"',
        response.text,
    )
    assert preview_match is not None
    with Image.open(io.BytesIO(base64.b64decode(preview_match.group(1)))) as preview:
        assert preview.size == (800, 1000)


def test_results_script_filters_exports_and_guards_navigation() -> None:
    root = Path(__file__).parents[1]
    script = (root / "app" / "static" / "results.js").read_text()
    styles = (root / "app" / "static" / "styles.css").read_text()
    assert 'card.dataset.resultStatus === filter' in script
    assert 'card.dataset.overwritten === "true"' in script
    assert "data-count-overwritten" in script
    assert "data-result-position" in script
    assert 'new Blob(["\\ufeff", lines.join("\\r\\n")]' in script
    assert "window.confirm" in script
    assert "These results have not been exported" in script
    assert 'window.history.pushState(resultsGuardState' in script
    assert 'window.addEventListener("popstate"' in script
    assert 'window.addEventListener("beforeunload"' in script
    assert 'link.target === "_blank"' in script
    assert "setDetailsExpanded" in script
    assert "Collapse All Details" in script
    assert 'window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" })' in script
    assert ".result-table tbody tr:nth-child(even)" in styles
    assert "imageViewer.showModal()" in script
    assert "event.target === imageViewer" in script
    assert "viewerClose.addEventListener" in script
    assert "updateOverallResult" in script
    assert "Overwritten: ${originalStatus} -> ${finalStatus}" in script
    assert 'row.final_result = finalStatus' in script
    assert 'row.overwritten = finalStatus !== originalStatus' in script
    assert '[data-theme="dark"] .status-pass' in styles
    assert "background: #78e3aa" in styles
    assert '[data-theme="dark"] .status-needs-review' in styles
    assert "background: #ffd06b" in styles
    assert '[data-theme="dark"] .status-fail' in styles
    assert "background: #ff8e96" in styles
    assert ".result-guidance-heading p" in styles
    assert "color: #40546a" in styles


def test_theme_script_persists_light_and_dark_modes() -> None:
    root = Path(__file__).parents[1]
    script = (root / "app" / "static" / "theme.js").read_text()
    styles = (root / "app" / "static" / "styles.css").read_text()
    assert 'localStorage.setItem("ttb-color-theme", theme)' in script
    assert 'root.dataset.theme === "dark" ? "light" : "dark"' in script
    assert '[data-theme="dark"]' in styles
    assert ".theme-icon-sun" in styles


def test_manual_batch_uses_application_data_for_each_file(monkeypatch) -> None:
    lines = [
        "FIRST BRAND",
        "Lager Beer",
        "5% ABV",
        "355 mL",
        "First Brewery, Austin, TX",
        GOVERNMENT_WARNING,
    ]
    fake_ocr = OcrResult(
        fragments=[OcrFragment(text=line, confidence=0.96) for line in lines],
        text="\n".join(lines),
        average_confidence=0.96,
    )
    monkeypatch.setattr(ocr_service, "extract", lambda image: fake_ocr)
    applications = [
        {
            "file_name": "front.png",
            "beverage_type": "beer_malt",
            "brand_name": "FIRST BRAND",
            "class_type": "Lager Beer",
            "alcohol_content": "5% ABV",
            "net_contents": "355 mL",
            "bottler_name_address": "First Brewery, Austin, TX",
        },
        {
            "file_name": "back.png",
            "beverage_type": "wine",
            "brand_name": "SECOND BRAND",
            "class_type": "Red Wine",
            "alcohol_content": "13% ABV",
            "net_contents": "750 mL",
            "bottler_name_address": "Second Winery, Napa, CA",
        },
    ]

    with TestClient(app) as client:
        response = client.post(
            "/verify",
            files=[
                ("images", ("front.png", _png(), "image/png")),
                ("images", ("back.png", _png(), "image/png")),
            ],
            data={"manual_applications": json.dumps(applications)},
        )

    assert response.status_code == 200
    assert "front.png" in response.text
    assert "back.png" in response.text
    assert "status-pass" in response.text
    assert "status-fail" in response.text


def test_batch_ocr_defaults_to_sequential_processing_and_preserves_order(monkeypatch) -> None:
    lines = [
        "TEST BRAND",
        "Lager Beer",
        "5% ABV",
        "355 mL",
        "Test Brewery, Austin, TX",
        GOVERNMENT_WARNING,
    ]
    fake_ocr = OcrResult(
        fragments=[OcrFragment(text=line, confidence=0.96) for line in lines],
        text="\n".join(lines),
        average_confidence=0.96,
    )
    lock = threading.Lock()
    active = 0
    peak = 0

    def fake_extract(image) -> OcrResult:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            time.sleep(0.02)
            return fake_ocr
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(ocr_service, "extract", fake_extract)
    file_names = ["first.png", "second.png", "third.png"]
    applications = [
        {
            "file_name": file_name,
            "beverage_type": "beer_malt",
            "brand_name": "TEST BRAND",
            "class_type": "Lager Beer",
            "alcohol_content": "5% ABV",
            "net_contents": "355 mL",
            "bottler_name_address": "Test Brewery, Austin, TX",
        }
        for file_name in file_names
    ]

    with TestClient(app) as client:
        response = client.post(
            "/verify",
            files=[("images", (file_name, _png(), "image/png")) for file_name in file_names],
            data={"manual_applications": json.dumps(applications)},
        )

    assert response.status_code == 200
    assert peak == 1
    assert response.text.index("first.png") < response.text.index("second.png")
    assert response.text.index("second.png") < response.text.index("third.png")
