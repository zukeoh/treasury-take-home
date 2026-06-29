"""FastAPI entrypoint and request orchestration for the pre-screener."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import config
from app.csv_service import CsvValidationError, parse_application_csv
from app.extraction_service import extract_fields
from app.image_service import ImageValidationError, create_result_preview_data_url, prepare_image
from app.manual_service import ManualValidationError, parse_manual_applications
from app.models import ApplicationData, LabelResult, Status
from app.ocr_service import OcrUnavailableError, ocr_service
from app.references import TTB_REFERENCE_GROUPS
from app.verification_service import unreadable_fields, verify_application


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.SKIP_OCR_INIT:
        try:
            await asyncio.to_thread(ocr_service.initialize)
        except OcrUnavailableError:
            logger.exception("Local OCR initialization failed")
    app.state.ocr_service = ocr_service
    yield


app = FastAPI(
    title=config.APP_NAME,
    version=config.APP_VERSION,
    description="Local OCR and deterministic pre-screening for alcohol beverage labels.",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
templates = Jinja2Templates(directory=config.TEMPLATES_DIR)
templates.env.globals["ttb_reference_groups"] = TTB_REFERENCE_GROUPS

EXPORT_COLUMNS = (
    "file_name",
    "beverage_type",
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "bottler_name_address",
    "imported",
    "country_of_origin",
    "beer_special_disclosure",
    "wine_appellation",
    "wine_sulfite_declaration",
    "spirits_age_statement",
    "spirits_commodity_statement",
    "original_result",
    "final_result",
    "overwritten",
)


def _render_index(
    request: Request,
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": config.APP_NAME,
            "error": error,
            "max_images": config.MAX_IMAGES,
            "max_image_mb": config.MAX_IMAGE_BYTES // (1024 * 1024),
        },
        status_code=status_code,
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return _render_index(request)


@app.get("/health", response_class=JSONResponse)
async def health(request: Request) -> JSONResponse:
    service = getattr(request.app.state, "ocr_service", ocr_service)
    return JSONResponse(
        {
            "status": "ok" if service.ready else "degraded",
            "ocr_ready": service.ready,
            "version": config.APP_VERSION,
        },
        status_code=200 if service.ready or config.SKIP_OCR_INIT else 503,
    )


@app.get("/sample.csv", response_class=PlainTextResponse)
async def sample_csv() -> PlainTextResponse:
    content = (
        "file_name,beverage_type,brand_name,product_type,abv,net_contents,producer,"
        "country_of_origin,beer_special_disclosure,wine_appellation,"
        "wine_sulfite_declaration,spirits_age_statement,spirits_commodity_statement\n"
        'old_tom_front.png,distilled_spirits,Old Tom Distillery,'
        'Kentucky Straight Bourbon Whiskey,45,750 mL,'
        '"Old Tom Distillery, Louisville, KY",,,,,,\n'
        'casa_azul.png,distilled_spirits,Casa Azul,Tequila,40,750 mL,'
        '"Casa Azul Imports, Austin, TX",Mexico,,,,,\n'
    )
    return PlainTextResponse(
        content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ttb-applications-sample.csv"'},
    )


def _review_result(
    file_name: str,
    message: str,
    elapsed_ms: int = 0,
    application: ApplicationData | None = None,
    image_preview_url: str | None = None,
) -> LabelResult:
    return LabelResult(
        file_name=file_name,
        status=Status.NEEDS_REVIEW,
        application=application,
        image_preview_url=image_preview_url,
        processing_time_ms=elapsed_ms,
        error=message,
    )


def _export_rows(results: list[LabelResult]) -> list[dict[str, str | bool]]:
    rows: list[dict[str, str | bool]] = []
    for result in results:
        application = (
            result.application.model_dump(mode="json") if result.application is not None else {}
        )
        row: dict[str, str | bool] = {
            column: application.get(column, "") for column in EXPORT_COLUMNS
        }
        row["file_name"] = result.file_name
        row["original_result"] = result.status.value
        row["final_result"] = result.status.value
        row["overwritten"] = False
        rows.append(row)
    return rows


@app.post("/verify", response_class=HTMLResponse)
async def verify(
    request: Request,
    images: list[UploadFile] = File(default=[]),
    application_csv: UploadFile | None = File(default=None),
    manual_applications: str = Form(default=""),
) -> HTMLResponse:
    valid_images = [image for image in images if image.filename]
    if not valid_images:
        return _render_index(request, "Choose at least one JPEG or PNG label image.", 400)
    if len(valid_images) > config.MAX_IMAGES:
        return _render_index(
            request,
            f"This prototype accepts up to {config.MAX_IMAGES} images in one batch.",
            400,
        )
    uploaded_names = [Path(image.filename or "unnamed-image").name for image in valid_images]
    if len({name.casefold() for name in uploaded_names}) != len(uploaded_names):
        return _render_index(
            request,
            "Each uploaded image must have a unique file name.",
            400,
        )

    applications: dict[str, ApplicationData] | None = None
    if application_csv and application_csv.filename:
        csv_bytes = await application_csv.read(2 * 1024 * 1024 + 1)
        if len(csv_bytes) > 2 * 1024 * 1024:
            return _render_index(request, "CSV exceeds the 2 MB limit.", 400)
        try:
            applications = parse_application_csv(csv_bytes)
        except CsvValidationError as exc:
            return _render_index(request, str(exc), 400)
    else:
        try:
            applications = parse_manual_applications(manual_applications)
        except ManualValidationError as exc:
            return _render_index(request, str(exc), 400)
        missing = [name for name in uploaded_names if name.casefold() not in applications]
        if missing:
            return _render_index(
                request,
                "Add application data for every image: " + ", ".join(missing) + ".",
                400,
            )

    batch_started = time.perf_counter()
    total_bytes = 0
    results: list[LabelResult] = []
    service = getattr(request.app.state, "ocr_service", ocr_service)

    for upload in valid_images:
        started = time.perf_counter()
        file_name = Path(upload.filename or "unnamed-image").name
        application = applications.get(file_name.casefold()) if applications else None
        image_preview_url: str | None = None
        if application is None:
            results.append(
                _review_result(
                    file_name,
                    "No application row matched this file name. Add an exact file_name entry and try again.",
                )
            )
            continue

        try:
            data = await upload.read(config.MAX_IMAGE_BYTES + 1)
            total_bytes += len(data)
            if total_bytes > config.MAX_TOTAL_BYTES:
                results.append(
                    _review_result(
                        file_name,
                        "The combined batch exceeds the 100 MB request limit.",
                        application=application,
                    )
                )
                continue
            prepared = await asyncio.to_thread(
                prepare_image,
                data,
                file_name,
                upload.content_type,
            )
            image_preview_url = create_result_preview_data_url(prepared)
            ocr = await asyncio.to_thread(service.extract, prepared)
            elapsed = round((time.perf_counter() - started) * 1000)
            if not ocr.fragments:
                results.append(
                    LabelResult(
                        file_name=file_name,
                        status=Status.NEEDS_REVIEW,
                        application=application,
                        image_preview_url=image_preview_url,
                        processing_time_ms=elapsed,
                        confidence=0,
                        fields=unreadable_fields(application),
                        extracted_text="",
                        error="No readable text was found. Try a flatter, sharper, evenly lit image.",
                    )
                )
                continue
            extracted = extract_fields(ocr, application)
            status, fields = verify_application(application, extracted, ocr)
            results.append(
                LabelResult(
                    file_name=file_name,
                    status=status,
                    application=application,
                    image_preview_url=image_preview_url,
                    processing_time_ms=elapsed,
                    confidence=ocr.average_confidence,
                    fields=fields,
                    extracted_text=ocr.text,
                )
            )
        except ImageValidationError as exc:
            elapsed = round((time.perf_counter() - started) * 1000)
            results.append(_review_result(file_name, str(exc), elapsed, application))
        except OcrUnavailableError:
            elapsed = round((time.perf_counter() - started) * 1000)
            logger.exception("Local OCR unavailable while processing an upload")
            results.append(
                _review_result(
                    file_name,
                    "The local OCR engine is temporarily unavailable. Please retry shortly.",
                    elapsed,
                    application,
                    image_preview_url,
                )
            )
        except Exception:
            elapsed = round((time.perf_counter() - started) * 1000)
            logger.exception("Unexpected label processing error")
            results.append(
                _review_result(
                    file_name,
                    "This image could not be processed. Confirm it is a valid JPEG or PNG and try again.",
                    elapsed,
                    application,
                    image_preview_url,
                )
            )

    batch_ms = round((time.perf_counter() - batch_started) * 1000)
    counts = {status.value: sum(result.status == status for result in results) for status in Status}
    return templates.TemplateResponse(
        request=request,
        name="results.html",
        context={
            "app_name": config.APP_NAME,
            "results": results,
            "counts": counts,
            "batch_ms": batch_ms,
            "export_columns": EXPORT_COLUMNS,
            "export_rows": _export_rows(results),
        },
    )
