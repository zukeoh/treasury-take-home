# TTB Alcohol Label Pre-Screener

TTB Alcohol Label Pre-Screener is a deployable proof of concept that compares alcohol beverage label artwork against expected application data. It uses selectable local OCR engines and deterministic validation rules to return explainable PASS, FAIL, or NEEDS REVIEW results for each label field. The prototype requires no API keys, hosted AI service, or database, and it does not persist uploaded label data.

> This is a decision-support prototype, not a COLA approval system or legal determination.

The original take-home prompt is preserved in [`instructions/README.md`](instructions/README.md).

## Live Demo

**Live app:** [https://treasury-take-home-4wq7.onrender.com/](https://treasury-take-home-4wq7.onrender.com/)

## Interface

Start a review by adding JPEG or PNG label artwork and entering application data manually or by CSV.

![Start review page](docs/screenshots/start-review.png)

Results summarize the batch and explain each field-level decision. Reviewers can filter outcomes, inspect OCR evidence, record an image-level override, and export CSV results.

![Review results page](docs/screenshots/review-results.png)

## Quick Start

### Docker

Docker is the most reproducible path because the image includes English EasyOCR model weights and the Tesseract system package.

```bash
docker build -t ttb-label-pre-screener .
docker run --rm -p 8000:8000 ttb-label-pre-screener
```

Open [http://localhost:8000](http://localhost:8000). The health endpoint is `/healthz`.

### Native Python

Use Python 3.11. The first native EasyOCR run downloads its English model. Native Tesseract use also requires the `tesseract-ocr` system package. Neither engine requires an API key.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```

On macOS or Linux, activate with `source .venv/bin/activate`.

No environment variables are required. Optional deployment tuning is documented below.

## What It Does

| Area | Behavior |
| --- | --- |
| Uploads | Accepts validated JPEG/PNG batches (configurable to 300), prevents duplicate filenames, and matches each image to manual or CSV application data. |
| OCR | Selects EasyOCR or Tesseract, resizes RGB inputs, gates concurrency across all requests, and sends weak/unreadable text to NEEDS REVIEW. A second enhanced pass is optional and off by default. |
| Verification | Fuzzy-matches identity fields, parses alcohol/proof and equivalent volumes, strictly evaluates the Government Health Warning, and checks supplied beverage-specific fields. |
| Results | Explains every field with expected/detected text, rationale, requirement basis, and TTB source; supports filtering, overrides, image inspection, and CSV export. |
| Data handling | Keeps uploads and results in request/browser memory. It uses no database, hosted inference endpoint, runtime API key, or persistent upload storage. |

## Architecture

```mermaid
flowchart TD
    B[Browser] --> E[Render HTTPS service<br/>or localhost:8000]

    subgraph APP[Single Docker container · Uvicorn worker: 1]
        F[FastAPI upload validation<br/>and CSV/manual matching]
        P[Pillow + OpenCV preprocessing]
        G[Process-wide concurrency gate]
        O[Selected local OCR provider<br/>EasyOCR or Tesseract]
        X[Expected-value-guided extraction]
        V[Deterministic verification rules]
        H[Explainable HTML results<br/>and browser-side CSV export]

        F --> P --> G --> O --> X --> V --> H
    end

    E --> F
```

Render belongs in the diagram as the hosted deployment boundary, not as an application component. Local Docker and Render run the same container and single Uvicorn process.

The selected OCR provider is initialized once per process under a lock. EasyOCR reuses one reader; Tesseract reuses the installed binary. A process-wide executor and semaphore cap OCR across all simultaneous requests. The application default is two OCR jobs; `render.yaml` explicitly lowers this to one for predictable memory use on a small hosted instance.

Images are decoded, converted to owned RGB buffers, and resized before OCR. The optional second OCR pass creates extra grayscale/OpenCV buffers only when enabled. Request-scoped logs record an ID, numbered stages, timings, current and peak RSS, cleanup, export construction, and template rendering. Traces contain metadata only—not images, previews, OCR text, or arrays.

Batch verification remains one synchronous HTTP request. Gated concurrency helps small and moderate batches, but 200–300 image production jobs need a durable queue, controlled workers, progress updates, retries, and resumable results.

Core stack: Python 3.11, FastAPI, Uvicorn, Jinja2, local Bootstrap 5.3, EasyOCR, Tesseract/pytesseract, CPU-only PyTorch in Docker, OpenCV, Pillow, RapidFuzz, Pydantic, and Pytest.

## Why Local OCR

Local OCR keeps evaluator setup predictable and avoids hosted inference, API keys, and per-request model cost. Deterministic Python rules make each status traceable. Docker embeds the English EasyOCR weights and Tesseract language data; this enlarges the image and build time but removes runtime model downloads. These model files are application assets—uploaded labels are not persisted.

## OCR Engine Selection

The app supports two local OCR engines:

- **EasyOCR** is the application default and is generally more tolerant of angled, blurred, decorative, or otherwise difficult label photos.
- **Tesseract** uses less memory and starts faster on small CPU instances. Its preprocessing includes sparse-text segmentation, contrast normalization, dark-image inversion, adaptive thresholding, sharpening, a white border, and conservative deskewing.

The deployed Render demo selects Tesseract because EasyOCR also loads PyTorch and a neural model, increasing cold-start time, CPU use, and peak memory. Tesseract is the safer hosted choice on a low-tier plan, although recognition may be worse on difficult artwork. This is a resource tradeoff, not a claim that Tesseract is more accurate.

Set `OCR_ENGINE=easyocr` locally or on a larger instance for the stronger difficult-image engine. Invalid values log a warning and fall back to EasyOCR. `/healthz`, result cards, and CSV exports report the selected engine.

Neither engine requires an API key, hosted OCR account, or network request at runtime.

## CSV Batch Format

The CSV must be UTF-8 and contain the required columns below. `beverage_type` is optional when it can be inferred from `product_type`.

```csv
file_name,beverage_type,brand_name,product_type,abv,net_contents,producer,country_of_origin
old_tom_front.png,distilled_spirits,Old Tom Distillery,Kentucky Straight Bourbon Whiskey,45,750 mL,"Old Tom Distillery, Louisville, KY",
casa_azul.png,distilled_spirits,Casa Azul,Tequila,40,750 mL,"Casa Azul Imports, Austin, TX",Mexico
```

- `file_name` matching is case-insensitive and otherwise exact.
- `abv` accepts a number such as `45` or a formatted value such as `45% ABV`.
- Leave `country_of_origin` blank for domestic products; a value marks the row as imported.
- Accepted `beverage_type` values are `beer_malt`, `wine`, and `distilled_spirits`.
- Optional category fields are `beer_special_disclosure`, `wine_appellation`, `wine_sulfite_declaration`, `spirits_age_statement`, and `spirits_commodity_statement`.
- Missing image rows return NEEDS REVIEW for the affected image. Invalid schemas, duplicates, and incomplete rows return a form-level error.
- Download a ready-to-edit example from `/sample.csv`.

The original build-plan column names remain accepted for backward compatibility.

## Decision Rules

### Flexible Fields

Brand, class/type, producer/address, country, and entered conditional statements use normalized fuzzy similarity. Case, punctuation, spacing, and complete token reordering do not cause an automatic failure, but missing expected words reduce the score.

### Structured Quantities

Alcohol and net contents are parsed as typed quantities rather than compared as raw strings. Equivalent values pass; numeric mismatches fail. An incomplete alcohol statement may need review.

### Beverage-Specific Fields

Selecting beer/malt beverage, wine, or distilled spirits reveals the relevant conditional fields. A supplied expected value is verified. A blank optional field is not treated as proof that the legal requirement is inapplicable.

### Government Health Warning

For beverages at or above 0.5% ABV, the checker validates the statutory wording, ordered similarity, required-word coverage, an all-caps `GOVERNMENT WARNING` heading, and warning-specific OCR confidence.

- PASS: the complete statutory warning matches exactly, including wording, punctuation, and capitalization; OCR line breaks and repeated whitespace are ignored.
- NEEDS REVIEW: the warning is not exact but at least 75% of its required words are present, or an exact match has low OCR confidence. Missing or non-uppercase heading text is called out for manual review but does not change this ≥75% result to FAIL.
- FAIL: the warning is missing or has less than 75% required-word coverage. A different failed field still keeps the overall label result at FAIL.

Physical typography—including minimum type size, bold heading, continuous-paragraph layout, and character density—cannot be established reliably without scale metadata and layout analysis. It appears as an informational NEEDS REVIEW row that does not lower an otherwise automated PASS.

### Overall Result

- FAIL if any required automated field fails.
- NEEDS REVIEW if no field fails but at least one required field is ambiguous.
- PASS only when all required automated fields pass.

## TTB References

- [Beer / Malt Beverage Labeling](https://www.ttb.gov/regulated-commodities/beverage-alcohol/beer/labeling)
- [Distilled Spirits Labeling](https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/labeling)
- [Wine Labeling](https://www.ttb.gov/regulated-commodities/beverage-alcohol/wine/labeling)
- [Malt Beverage Health Warning](https://www.ttb.gov/regulated-commodities/beverage-alcohol/beer/labeling/malt-beverage-health-warning)
- [Distilled Spirits Health Warning](https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/ds-labeling-home/ds-health-warning)
- [Wine Health Warning](https://www.ttb.gov/regulated-commodities/beverage-alcohol/wine/labeling-wine/wine-labeling-health-warning-statement)

See [`docs/rule_documentation.md`](docs/rule_documentation.md) for field-level implementation bases and source mapping.

## Render Deployment

`render.yaml` defines a Docker web service and `/healthz` check.

No environment variables are required for the prototype. Optional tuning variables are listed below.

| Variable | Default | Purpose |
| --- | ---: | --- |
| `OCR_ENGINE` | `easyocr` | Selects `easyocr` or `tesseract` |
| `OCR_MAX_WORKERS` | `2` | Limits concurrent OCR jobs across all requests |
| `LOG_LEVEL` | `INFO` | Logging level |
| `MAX_IMAGE_BYTES` | `12582912` | Per-image upload limit |
| `MAX_TOTAL_BYTES` | `104857600` | Total request upload limit |
| `MAX_IMAGES` | `300` | Max images per batch |
| `MAX_IMAGE_DIMENSION` | `3200` | Absolute preprocessing dimension cap |
| `MAX_OCR_IMAGE_DIMENSION` | `1600` | OCR long-edge resize target |
| `ENABLE_SECOND_OCR_PASS` | `false` | Enables the enhanced retry for weak OCR |
| `OCR_GPU` | `false` | Enables GPU OCR if available |
| `TESSERACT_PSM` | `11` | Sparse-text segmentation mode for label layouts |
| `TESSERACT_DESKEW` | `true` | Corrects detected skew up to 15 degrees |

`EASYOCR_MODEL_DIR` may also override the model location for a native deployment. Docker already sets it to the model directory embedded during the image build. `PYTHONUNBUFFERED=1` is set by the Dockerfile.

The Render blueprint overrides the application defaults with `OCR_ENGINE=tesseract`, `OCR_MAX_WORKERS=1`, and no second pass. This reduces cold-start pressure, peak memory, and concurrent inference risk. The settings are optional tuning values, not secrets.

1. Push the repository to GitHub.
2. In Render, choose **New → Blueprint**.
3. Connect the repository and apply `render.yaml`.
4. Wait for the image, OCR assets, and dependencies to build.
5. Confirm `/healthz` and open the service URL.

The deployed Render service is usable immediately after build. Evaluators do not need to provide API keys, configure storage, or set environment variables.

Docker and Render both use one Uvicorn worker (`--workers 1`). Tesseract is recommended on Render because it avoids loading EasyOCR/PyTorch into runtime memory. A Starter instance remains an operational recommendation rather than an application requirement. The service needs no secret, database, persistent disk, or runtime model download.

The same container can later be evaluated for Azure Container Apps or Azure App Service. Federal production deployment would still require agency review for identity, audit, retention, accessibility, and security controls.

## Testing

```bash
pip install -r requirements-test.txt
pytest
```

The suite contains 59 fast tests for rules, parsing, uploads, exports, OCR providers, concurrency, tracing, preprocessing, health checks, and deployment defaults. Three opt-in tests run the real Tesseract binary against generated fixtures.

```powershell
docker run --rm -e PYTHONPATH=/workspace -e RUN_TESSERACT_FIXTURE_TESTS=1 -e MAX_OCR_IMAGE_DIMENSION=1600 -e TESSERACT_PSM=11 -e TESSERACT_DESKEW=true -v "${PWD}:/workspace" -w /workspace --entrypoint python ttb-label-pre-screener:local tests/test_tesseract_fixture_quality.py
```

`tests/resources/sample_data/` contains 50 generated labels and three CSV batches. `batch_mixed.csv` covers all images; the other batches target clean-to-moderate and severe/failing cases. Dataset realism limits are documented below.

## Security and Data Handling

- Uploaded files and application data are read into memory for the active request and are not persisted by the application.
- Result previews are bounded JPEG data URLs returned in the HTML response and retained only in the browser page.
- OCR text and overrides are not stored server-side.
- Request traces retain only identifiers, timings, counts, dimensions, and memory measurements—not OCR text, images, previews, or arrays.
- The container includes application code, dependencies, EasyOCR weights, and Tesseract language data; those model files are not user data.
- Image type, decoded format, size, total request size, and pixel count are validated before OCR.
- No live COLA access, authentication, approval action, or external inference service is included.

## Assumptions and Tradeoffs

Manual or CSV values stand in for trusted COLA application data. PASS, FAIL, and NEEDS REVIEW are pre-screening outcomes; a human remains the decision-maker.

| Choice | Benefit | Cost / boundary |
| --- | --- | --- |
| Local OCR + deterministic rules | No API keys or per-request model cost; explainable outcomes | Less flexible than general document understanding |
| EasyOCR as the application default | Better tolerance for difficult photos | PyTorch increases image size, startup time, CPU, and memory |
| Tesseract on Render | Lower, more predictable hosted resource use | Lower accuracy on severe angles, blur, decoration, and curvature |
| Gated OCR concurrency | Prevents unbounded inference across simultaneous requests | Application default `2`; Render uses `1`, so batches may take longer |
| Embedded OCR assets | No runtime model download or hosted dependency | Larger Docker image and slower build |
| In-memory request processing | Simple deployment with no database or storage secrets | No durable job state, resume, server-side audit history, or recovery after restart |
| Expected-value-guided extraction | Strong evidence for field-by-field comparison | Depends on correct application data and is not open-ended label interpretation |
| Synchronous batch response | Simple evaluator workflow | Unsuitable for production-scale 200–300 image jobs without a queue |

## Known Limitations

| Limitation | Effect | Production direction |
| --- | --- | --- |
| Synchronous processing | Large or difficult batches may exceed an HTTP timeout; `MAX_IMAGES=300` is an acceptance limit, not a throughput guarantee | Durable queue, progress events, retries, cancellation, and resumable results |
| OCR image quality | Severe glare, curvature, decorative fonts, extreme skew, blur, mirroring, or crops can hide required text | Better capture guidance, layout-aware preprocessing, stronger OCR, and human review |
| Unscaled artwork | Physical type size, character density, and some layout requirements cannot be proven | Require scale metadata or source artwork and add layout measurement |
| Incomplete application context | Optional commodity rules are checked only when the expected field is supplied | Integrate trusted COLA data and expand rule coverage |
| No production controls | No login, role-based access, durable audit log, retention policy, monitoring, or live COLA integration | Complete agency security, privacy, accessibility, and operations review |

### Test-data limitation

The 50 generated labels deliberately vary beverage category, wording errors, damage, lighting, rotation, cropping, scale, mirroring, perspective, and layout. However, they come from one synthetic generator and reuse related fonts, drawing primitives, warning construction, image dimensions, and rendering assumptions. Some fixtures are therefore more visually similar and predictable than independently photographed labels.

The fixtures are useful for repeatable regression tests, not for claiming real-world accuracy. A production evaluation needs a larger, de-identified, human-reviewed corpus spanning printers, containers, materials, cameras, languages, typography, multi-panel artwork, natural backgrounds, and naturally occurring damage.

## Future Improvements

1. Add a durable queue with progress events, retries, cancellation, and resumable jobs for large batches.
2. Add authenticated COLA application lookup and role-based access.
3. Add structured audit events, retention controls, and deployment monitoring.
4. Expand layout-aware OCR for multi-panel labels and physical typography checks.
5. Add an AI-assisted second-review stage for OCR-generated FAIL and NEEDS REVIEW cases.
6. Calibrate field thresholds against a representative reviewed-label corpus.
7. Complete accessibility and agency security testing for the target hosting environment.

### Why AI is not in this POC

Local OCR and deterministic rules can handle the majority of expected labels faster and more cheaply, without per-request model cost or added infrastructure. Applying AI to every review would add credentials or a large local model, latency, operational and data-handling complexity, nondeterministic output, hallucination risk, and a separate accuracy/bias evaluation.

A production follow-up could use an agency-approved model only as a second reviewer for OCR-generated FAIL and NEEDS REVIEW cases. It could compare the image, OCR text, expected values, and rule evidence, then suggest likely OCR corrections. Confidence gates, redaction and retention controls, prompt/model version logs, and human confirmation would be required; AI should not silently override statutory rules or issue approval.
