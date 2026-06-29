"""FastAPI entrypoint and request orchestration for the pre-screener."""

from __future__ import annotations

import asyncio
import gc
import logging
import time
from concurrent.futures import ThreadPoolExecutor
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
from app.ocr_service import OcrService, OcrUnavailableError, ocr_service
from app.references import TTB_REFERENCE_GROUPS
from app.telemetry import RequestTrace
from app.verification_service import unreadable_fields, verify_application


logger = logging.getLogger(__name__)
logger.setLevel(config.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One process-wide executor gates OCR across concurrent requests. The OCR
    # service has a second boundary-level semaphore to protect the shared reader.
    executor = ThreadPoolExecutor(
        max_workers=config.OCR_MAX_WORKERS,
        thread_name_prefix="ttb-ocr",
    )
    app.state.ocr_executor = executor
    app.state.ocr_service = ocr_service
    try:
        if not config.SKIP_OCR_INIT:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(executor, ocr_service.initialize)
            except OcrUnavailableError:
                logger.exception("Local OCR initialization failed")
        yield
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


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
    "ocr_engine",
    "ocr_elapsed_ms",
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


@app.get("/healthz", response_class=JSONResponse)
async def health(request: Request) -> JSONResponse:
    service = getattr(request.app.state, "ocr_service", ocr_service)
    return JSONResponse(
        {
            "status": "ok" if service.ready else "degraded",
            "ocr_ready": service.ready,
            "ocr_engine": service.engine,
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
    ocr_engine: str = "",
) -> LabelResult:
    return LabelResult(
        file_name=file_name,
        status=Status.NEEDS_REVIEW,
        application=application,
        image_preview_url=image_preview_url,
        processing_time_ms=elapsed_ms,
        ocr_engine=ocr_engine,
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
        row["ocr_engine"] = result.ocr_engine
        row["ocr_elapsed_ms"] = result.ocr_elapsed_ms
        row["original_result"] = result.status.value
        row["final_result"] = result.status.value
        row["overwritten"] = False
        rows.append(row)
    return rows


async def _process_upload(
    upload: UploadFile,
    application: ApplicationData | None,
    service: OcrService,
    ocr_executor: ThreadPoolExecutor,
    worker_limit: asyncio.Semaphore,
    batch_bytes: list[int],
    trace: RequestTrace,
    image_index: int,
    image_count: int,
) -> LabelResult:
    """Process one image while respecting the request and process OCR limits."""

    async with worker_limit:
        started = time.perf_counter()
        file_name = Path(upload.filename or "unnamed-image").name
        image_context = f"image={image_index}/{image_count} filename={file_name}"
        image_preview_url: str | None = None
        data: bytes | None = None
        prepared = None
        ocr = None
        extracted = None
        fields = None
        trace.info("Processing image %d/%d", image_index, image_count)
        trace.info("Filename: %s", file_name)
        if application is None:
            await upload.close()
            trace.info("No application data matched | %s", image_context)
            trace.stage(10, "Cleanup", image_context)
            trace.info("Running gc.collect() | %s", image_context)
            collected = gc.collect()
            trace.info("gc.collect() complete | Objects collected: %d | %s", collected, image_context)
            trace.mark("after_cleanup", image_context)
            trace.timing("Total image time", started, image_context)
            return _review_result(
                file_name,
                "No application row matched this file name. Add an exact file_name entry and try again.",
                ocr_engine=service.engine,
            )

        try:
            trace.stage(1, "Loading image", image_context)
            trace.mark("before_image_load", image_context)
            with trace.time_block("Image load", image_context):
                try:
                    data = await upload.read(config.MAX_IMAGE_BYTES + 1)
                finally:
                    await upload.close()
            trace.info("File size: %.2f MB | %s", len(data) / (1024 * 1024), image_context)
            trace.mark("after_image_load", image_context)
            # This update has no await between read and write, so request tasks cannot
            # interleave while changing the shared counter.
            batch_bytes[0] += len(data)
            if batch_bytes[0] > config.MAX_TOTAL_BYTES:
                limit_mb = config.MAX_TOTAL_BYTES // (1024 * 1024)
                return _review_result(
                    file_name,
                    f"The combined batch exceeds the {limit_mb} MB request limit.",
                    application=application,
                    ocr_engine=service.engine,
                )

            with trace.time_block("Image preprocessing", image_context):
                prepared = await asyncio.to_thread(
                    prepare_image,
                    data,
                    file_name,
                    upload.content_type,
                    trace,
                    image_context,
                )
            data = None

            trace.mark("before_preview_creation", image_context)
            with trace.time_block("Preview creation", image_context):
                image_preview_url = await asyncio.to_thread(
                    create_result_preview_data_url,
                    prepared,
                )
            trace.mark("after_preview_creation", image_context)

            loop = asyncio.get_running_loop()
            ocr = await loop.run_in_executor(
                ocr_executor,
                service.extract,
                prepared,
                trace,
                image_context,
            )
            trace.mark("after_text_extraction", image_context)
            elapsed = round((time.perf_counter() - started) * 1000)
            if not ocr.fragments:
                fields = unreadable_fields(application)
                return LabelResult(
                    file_name=file_name,
                    status=Status.NEEDS_REVIEW,
                    application=application,
                    image_preview_url=image_preview_url,
                    processing_time_ms=elapsed,
                    confidence=0,
                    ocr_engine=ocr.engine if ocr.engine != "unknown" else service.engine,
                    ocr_elapsed_ms=ocr.elapsed_ms,
                    fields=fields,
                    extracted_text="",
                    error="No readable text was found. Try a flatter, sharper, evenly lit image.",
                )

            trace.stage(7, "Parse fields", image_context)
            with trace.time_block("Field parsing", image_context):
                extracted = extract_fields(ocr, application)
            trace.mark("after_field_parsing", image_context)

            trace.stage(8, "Verify fields", image_context)
            with trace.time_block("Verification", image_context):
                status, fields = verify_application(application, extracted, ocr)
            trace.mark("after_verification", image_context)
            return LabelResult(
                file_name=file_name,
                status=status,
                application=application,
                image_preview_url=image_preview_url,
                processing_time_ms=elapsed,
                confidence=ocr.average_confidence,
                ocr_engine=ocr.engine if ocr.engine != "unknown" else service.engine,
                ocr_elapsed_ms=ocr.elapsed_ms,
                fields=fields,
                extracted_text=ocr.text,
            )
        except ImageValidationError as exc:
            elapsed = round((time.perf_counter() - started) * 1000)
            trace.exception("Image preprocessing failed | %s", image_context)
            return _review_result(
                file_name,
                str(exc),
                elapsed,
                application,
                ocr_engine=service.engine,
            )
        except OcrUnavailableError:
            elapsed = round((time.perf_counter() - started) * 1000)
            trace.exception("OCR failed: local OCR unavailable | %s", image_context)
            return _review_result(
                file_name,
                "The local OCR engine is temporarily unavailable. Please retry shortly.",
                elapsed,
                application,
                image_preview_url,
                service.engine,
            )
        except Exception:
            elapsed = round((time.perf_counter() - started) * 1000)
            trace.exception("Unexpected image processing failure | %s", image_context)
            return _review_result(
                file_name,
                "This image could not be processed. Confirm it is a valid JPEG or PNG and try again.",
                elapsed,
                application,
                image_preview_url,
                service.engine,
            )
        finally:
            trace.stage(10, "Cleanup", image_context)
            trace.info("Deleting OpenCV/NumPy image buffers | %s", image_context)
            prepared = None
            data = None
            trace.info("Deleting Pillow image references (released during preprocessing) | %s", image_context)
            trace.info("Deleting OCR result objects | %s", image_context)
            ocr = None
            extracted = None
            fields = None
            trace.info("Running gc.collect() | %s", image_context)
            collected = gc.collect()
            trace.info("gc.collect() complete | Objects collected: %d | %s", collected, image_context)
            trace.mark("after_cleanup", image_context)
            trace.timing("Total image time", started, image_context)


@app.post("/verify", response_class=HTMLResponse)
async def verify(
    request: Request,
    images: list[UploadFile] = File(default=[]),
    application_csv: UploadFile | None = File(default=None),
    manual_applications: str = Form(default=""),
) -> HTMLResponse:
    valid_images = [image for image in images if image.filename]
    trace = RequestTrace()
    trace.request_start(
        image_count=len(valid_images),
        csv_uploaded=bool(application_csv and application_csv.filename),
    )

    def render_validation_error(message: str, status_code: int = 400) -> HTMLResponse:
        trace.info("Request validation failed | %s", message)
        trace.stage(9, "Build response")
        trace.mark("before_response_render")
        with trace.time_block("Response rendering"):
            response = _render_index(request, message, status_code)
        trace.mark("after_response_render")
        trace.stage(11, "Response returned")
        trace.log_summary(0)
        return response

    if not valid_images:
        return render_validation_error("Choose at least one JPEG or PNG label image.")
    if len(valid_images) > config.MAX_IMAGES:
        return render_validation_error(
            f"This prototype accepts up to {config.MAX_IMAGES} images in one batch.",
        )
    uploaded_names = [Path(image.filename or "unnamed-image").name for image in valid_images]
    if len({name.casefold() for name in uploaded_names}) != len(uploaded_names):
        return render_validation_error("Each uploaded image must have a unique file name.")

    applications: dict[str, ApplicationData] | None = None
    if application_csv and application_csv.filename:
        with trace.time_block("CSV load and parsing"):
            try:
                csv_bytes = await application_csv.read(2 * 1024 * 1024 + 1)
            finally:
                await application_csv.close()
        if len(csv_bytes) > 2 * 1024 * 1024:
            return render_validation_error("CSV exceeds the 2 MB limit.")
        try:
            applications = parse_application_csv(csv_bytes)
        except CsvValidationError as exc:
            trace.exception("CSV parsing failed")
            return render_validation_error(str(exc))
        finally:
            del csv_bytes
            trace.memory("After CSV cleanup")
    else:
        try:
            with trace.time_block("Manual application parsing"):
                applications = parse_manual_applications(manual_applications)
        except ManualValidationError as exc:
            trace.exception("Manual application parsing failed")
            return render_validation_error(str(exc))
        missing = [name for name in uploaded_names if name.casefold() not in applications]
        if missing:
            return render_validation_error(
                "Add application data for every image: " + ", ".join(missing) + "."
            )

    batch_started = time.perf_counter()
    trace.memory("Before batch processing")
    service = getattr(request.app.state, "ocr_service", ocr_service)
    executor = request.app.state.ocr_executor
    worker_limit = asyncio.Semaphore(config.OCR_MAX_WORKERS)
    batch_bytes = [0]
    results = await asyncio.gather(
        *(
            _process_upload(
                upload,
                applications.get(Path(upload.filename or "").name.casefold())
                if applications
                else None,
                service,
                executor,
                worker_limit,
                batch_bytes,
                trace,
                image_index,
                len(valid_images),
            )
            for image_index, upload in enumerate(valid_images, start=1)
        )
    )
    trace.memory("After batch processing")

    batch_ms = round((time.perf_counter() - batch_started) * 1000)
    counts = {status.value: sum(result.status == status for result in results) for status in Status}
    trace.stage(9, "Build response")
    trace.mark("before_export_build")
    with trace.time_block("Export data building"):
        export_rows = _export_rows(results)
    trace.info("Export rows built: %d", len(export_rows))
    trace.mark("after_export_build")

    trace.mark("before_response_render")
    try:
        with trace.time_block("Response rendering"):
            response = templates.TemplateResponse(
                request=request,
                name="results.html",
                context={
                    "app_name": config.APP_NAME,
                    "results": results,
                    "counts": counts,
                    "batch_ms": batch_ms,
                    "export_columns": EXPORT_COLUMNS,
                    "export_rows": export_rows,
                },
            )
    except Exception:
        trace.exception("Response creation failed")
        trace.log_summary(len(results))
        raise
    trace.mark("after_response_render")
    trace.memory("After response creation")
    trace.stage(11, "Response returned")
    trace.log_summary(len(results))
    return response
