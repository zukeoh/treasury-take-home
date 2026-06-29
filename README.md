# TTB Alcohol Label Pre-Screener

A deployable proof of concept that compares alcohol beverage label artwork with expected application data. It performs OCR locally, applies deterministic matching rules, and returns an explainable PASS, FAIL, or NEEDS REVIEW decision for every label.

> This is a decision-support prototype, not a COLA approval system or legal determination.

The original take-home prompt is preserved in [`instructions/README.md`](instructions/README.md). This document describes the implemented project, how to run it, and the engineering decisions behind it.

## Live Demo

**Render URL:** [Add deployed service URL](https://your-render-service.onrender.com)

The repository is deployment-ready. A Render account owner must create the service to produce the public URL.

## Why This Approach

The stakeholder interviews emphasized four constraints: routine matching should be fast, agents need to understand every decision, government networks may block outbound ML endpoints, and evaluators should not configure API keys. The prototype therefore uses local EasyOCR plus explicit validation rules. It sends no images or extracted text to hosted AI services and stores nothing after the request.

The Government Health Warning wording and heading rules are based on official TTB health-warning guidance, which points to 27 CFR part 16.

### Official TTB References

This prototype uses the following TTB labeling guidance pages as implementation references:

- Beer / Malt Beverage Labeling: [https://www.ttb.gov/regulated-commodities/beverage-alcohol/beer/labeling](https://www.ttb.gov/regulated-commodities/beverage-alcohol/beer/labeling)
- Distilled Spirits Labeling: [https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/labeling](https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/labeling)
- Wine Labeling: [https://www.ttb.gov/regulated-commodities/beverage-alcohol/wine/labeling](https://www.ttb.gov/regulated-commodities/beverage-alcohol/wine/labeling)
- Malt Beverage Health Warning: [https://www.ttb.gov/regulated-commodities/beverage-alcohol/beer/labeling/malt-beverage-health-warning](https://www.ttb.gov/regulated-commodities/beverage-alcohol/beer/labeling/malt-beverage-health-warning)
- Distilled Spirits Health Warning: [https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/ds-labeling-home/ds-health-warning](https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/ds-labeling-home/ds-health-warning)
- Wine Health Warning: [https://www.ttb.gov/regulated-commodities/beverage-alcohol/wine/labeling-wine/wine-labeling-health-warning-statement](https://www.ttb.gov/regulated-commodities/beverage-alcohol/wine/labeling-wine/wine-labeling-health-warning-statement)

The prototype implements common mandatory label checks and flags more complex conditional rules as NEEDS REVIEW when full product context is not available. See the [rule documentation](docs/rule_documentation.md) for field-level implementation bases and source mapping.

## What It Does

- Accepts JPEG and PNG artwork, from one image through a prototype batch of 300, with additive selections and removable thumbnail previews.
- Ignores a repeated filename without replacing data and briefly shakes and highlights its existing thumbnail.
- Creates a separate manual application form for every uploaded `file_name`, or accepts matching CSV rows.
- Reveals beer/malt beverage, wine, or distilled-spirits fields after the beverage type is selected.
- Validates image type, contents, size, and pixel dimensions.
- Resizes oversized images and uses contrast enhancement for a second OCR attempt when the first pass is weak.
- Fuzzy-matches names and addresses while ignoring capitalization, punctuation, spacing, and harmless OCR token reordering while still penalizing missing expected words.
- Normalizes alcohol statements such as `45% ABV`, `45% Alc./Vol.`, and `90 Proof`.
- Normalizes volume equivalents such as `750 mL` and `0.75 liter`.
- Strictly checks government warning wording, the all-caps heading, OCR confidence, and the 0.5% ABV applicability threshold.
- Shows expected text, detected text, status, and a plain-language explanation per field.
- Checks entered beverage-specific statements, including wine appellation and sulfites, spirits age and commodity statements, and beer/malt special disclosures when applicable.
- Transitions immediately to a Review Results loading view while in-memory OCR and verification run.
- Filters completed results by PASS, FAIL, NEEDS REVIEW, or overwritten status and exports entered application fields plus each image outcome to CSV.
- Lets an agent override each image's overall result while preserving its automated original result and recording the final result and overwritten flag in the export.
- Shows image previews beside filenames and opens a large top-layer comparison viewer from each completed result thumbnail.
- Provides per-result and global collapse controls, clearer outcome guidance, and a Scroll to Top shortcut for long reviews.
- Numbers visible result cards as their current position out of the selected filter's total.
- Estimates loading time at roughly 3.5 seconds per image while showing elapsed progress.
- Supports a persistent light/dark theme toggle across application and results pages.
- Uses high-contrast PASS, FAIL, and NEEDS REVIEW status chips in dark mode.
- Warns before same-tab links, browser Back, reload, or close abandon active processing or unexported results.
- Processes uploads in memory and does not persist input or output.

## Requirements And Implementation Traceability

| Requirement or stakeholder need | Implementation |
| --- | --- |
| Fast routine review | A process-wide EasyOCR reader avoids per-request model startup. OCR runs off the async event loop, and a second enhanced pass runs only when the first pass is weak. The UI estimates about 3.5 seconds per image based on observed prototype performance. |
| Simple, obvious UX | The workflow has two numbered steps, additive image thumbnails, filename-specific forms, keyboard navigation, clear outcome colors, collapsible details, image comparison, dark mode, and plain-language errors. Application data stays disabled until at least one image is selected. |
| Batch processing | The app accepts multiple images and either one manual form per filename or a matching CSV row per filename. The prototype limit is configurable and defaults to 300 images. |
| Imperfect images | Pillow and OpenCV validate, resize, normalize, and enhance images. Low confidence, unreadable text, crop, glare, or skew routes uncertain fields to NEEDS REVIEW instead of inventing a match. |
| Flexible human-equivalent matching | Brand, class/type, producer/address, country, and entered conditional statements use normalized fuzzy matching. Case, punctuation, and spacing differences such as `STONE'S THROW` versus `Stone's Throw` do not automatically fail. |
| Strict statutory warning | The Government Health Warning uses stricter wording and uppercase-heading checks, a warning-specific OCR confidence rule, and the 0.5% ABV applicability threshold. Unsupported physical typography checks are explicitly routed to human review. |
| Explainability | Every field shows expected text, detected text, status, explanation, requirement basis, and an official TTB source. Agents can override only the image-level final result; automated field findings remain visible. |
| Blocked outbound services | EasyOCR and its model run locally. Runtime verification requires no OpenAI key, hosted model endpoint, database, or external inference request. |
| Request-only data handling | Images, CSV data, OCR text, results, and overrides remain in request/browser memory. The app has no database or upload-retention path. |
| No COLA integration | Manual entry and CSV rows are explicit stand-ins for application data. Live COLA access, identity, and approval actions are out of scope. |
| Deployment path | Docker and Render configuration are included. The same container can later be evaluated for Azure App Service or Azure Container Apps after agency security review. |
| Human judgment | PASS, FAIL, and NEEDS REVIEW are pre-screening outcomes. Agents can choose a different overall final result, and CSV export preserves `original_result`, `final_result`, and `overwritten`. |

## Architecture

```text
Browser (local Bootstrap + Jinja)
        |
        v
FastAPI request validation
        |
        +--> CSV / manual application data
        |
        v
Pillow + OpenCV image validation and preprocessing
        |
        v
Process-wide EasyOCR reader (local model)
        |
        v
Expected-value-guided field extraction
        |
        v
Deterministic verification rules
        |
        v
Explainable HTML results (no persistence)
```

The EasyOCR reader initializes once during application startup. OCR work runs outside the async request loop, and a lock protects the shared reader. A low-confidence first pass triggers one enhanced grayscale pass; a confident image avoids that extra cost.

### Processing Flow And Performance

Each image is processed sequentially within the request:

1. Validate extension, decoded format, byte size, and pixel dimensions.
2. Convert to RGB and resize an oversized image for OCR.
3. Run local EasyOCR and collect text fragments and confidence values.
4. If confidence is weak, run one contrast-enhanced grayscale attempt and keep the stronger result.
5. Extract expected-value-guided field candidates from neighboring OCR fragments.
6. Apply deterministic fuzzy, numeric, strict-warning, and confidence rules.
7. Render field explanations and the image-level outcome.

The results-loading view appears immediately and estimates 3.5 seconds per image. That is a usability estimate, not a service-level guarantee: CPU, image dimensions, contrast, and whether the second OCR pass is needed all affect actual time. The completed results page reports measured per-image and batch processing times. Synchronous processing keeps the prototype easy to run and inspect; production-scale 200–300 image batches should move to a durable queue with real progress events and resumable jobs.

## Tech Stack

- Python 3.11
- FastAPI and Uvicorn
- Jinja2
- Bootstrap 5.3, vendored locally
- EasyOCR with CPU-only PyTorch in Docker
- OpenCV and Pillow
- RapidFuzz
- Pydantic
- Pytest
- Docker and Render Blueprint configuration

## Local Setup

EasyOCR downloads its English model on the first non-Docker run. No API key is required.

Prerequisites:

- Python 3.11 for a native run, or Docker Desktop for the containerized path.
- At least 1 GB of available memory; additional headroom is useful during OCR model initialization.
- Network access during the first native setup or Docker build so EasyOCR model weights and Python packages can be installed. The running container does not need a hosted AI service.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

On macOS or Linux, activate with `source .venv/bin/activate`. The application supports these optional environment variables:

| Variable | Default | Purpose |
| --- | ---: | --- |
| `OCR_GPU` | `false` | Enable a compatible EasyOCR GPU |
| `EASYOCR_MODEL_DIR` | EasyOCR default | Override the local model directory |
| `MAX_IMAGE_BYTES` | 12 MB | Per-image byte limit |
| `MAX_TOTAL_BYTES` | 100 MB | Combined request byte limit |
| `MAX_IMAGES` | 300 | Images accepted in one request |
| `MAX_IMAGE_DIMENSION` | 3200 px | Long-edge OCR resize target |

## Docker

The Docker build downloads model weights into the image. A running container therefore makes no outbound model or AI calls.

```bash
docker build -t ttb-label-verifier .
docker run --rm -p 8000:8000 ttb-label-verifier
```

Open [http://localhost:8000](http://localhost:8000). The health endpoint is `/health`.

The CPU-only OCR image is intentionally substantial because PyTorch and the English OCR weights are embedded. Allocate at least 1 GB memory to the container.

## Render Deployment

`render.yaml` defines a Docker web service and health check.

1. Push this repository to GitHub.
2. In Render, choose **New → Blueprint**.
3. Connect this repository and apply the detected `render.yaml`.
4. Wait for the Docker image and EasyOCR model to build.
5. Open `/health`, then place the service URL in the Live demo section above.

The Blueprint selects a Starter instance because EasyOCR/PyTorch can exceed the memory available to small free services. No secrets, database, persistent disk, or API keys are needed.

For a future federal-hosting path, the same image can run in Azure Container Apps or Azure App Service. Production work would still require agency security review, identity, audit, retention, accessibility, and FedRAMP controls.

## CSV Batch Format

The CSV must be UTF-8 and contain every required column below. `beverage_type` is optional because the app can infer it from `product_type`.

```csv
file_name,beverage_type,brand_name,product_type,abv,net_contents,producer,country_of_origin
old_tom_front.png,distilled_spirits,Old Tom Distillery,Kentucky Straight Bourbon Whiskey,45,750 mL,"Old Tom Distillery, Louisville, KY",
casa_azul.png,distilled_spirits,Casa Azul,Tequila,40,750 mL,"Casa Azul Imports, Austin, TX",Mexico
```

- `file_name` matching is case-insensitive and otherwise exact.
- `abv` accepts a number such as `45`, or a formatted value such as `45% ABV`.
- Leave `country_of_origin` blank for domestic products; a country value marks the row as imported.
- Accepted `beverage_type` values are `beer_malt`, `wine`, and `distilled_spirits`.
- Optional beverage-specific columns are `beer_special_disclosure`, `wine_appellation`, `wine_sulfite_declaration`, `spirits_age_statement`, and `spirits_commodity_statement`. A nonblank expected value is checked against OCR text.
- A missing image row affects only that image and returns NEEDS REVIEW.
- Duplicate filenames, missing columns, invalid booleans, and incomplete rows produce a clear form-level error.
- Download a ready-to-edit example from `/sample.csv` in the running app.

The original build-plan column names remain accepted for backward compatibility.

## Decision Rules

### Flexible Fields

Brand, class/type, producer/address, and country use normalized fuzzy similarity. This allows the stakeholder example `STONE'S THROW` to match `Stone's Throw` while still rejecting material differences. For skewed or multi-column labels, extraction can collect a bounded set of high-confidence fragments that contribute previously unseen expected tokens. Comparison accepts complete token reordering, such as `RUM SPICED BAYVIEW` for `BAYVIEW SPICED RUM`, but multiplies unordered similarity by expected-token coverage so missing words remain penalized. Thresholds vary by field because a multi-line producer address is naturally noisier than a short brand name.

### Structured Quantities

Alcohol and net contents are parsed to typed values rather than compared as raw strings. Equivalent formatting passes; a different numeric value fails. If only one of two expected alcohol measures is readable, the field needs review.

### Beverage-Specific Fields

Manual entry starts with an explicit beer/malt beverage, wine, or distilled-spirits selection for each image. The app then reveals only that category's additional fields. These requirements are conditional: for example, a wine appellation is required in specified labeling circumstances, and an age statement applies only to specified distilled spirits. The prototype validates a beverage-specific statement when the application data supplies an expected value; blank optional fields are not treated as proof that the underlying requirement is inapplicable.

### Government Warning

The application validates the required statutory Government Health Warning text, verifies that the `GOVERNMENT WARNING` heading appears in uppercase, and checks that the warning is present when required based on alcohol content. It searches all OCR text, so the warning may appear on the front, back, or side label included in the uploaded image.

The warning is required when the detected alcohol content is **0.5% ABV or greater**. A missing warning does not automatically fail a label when OCR establishes `0.0% ABV`, another value below 0.5%, or a non-alcoholic designation. A conflicting application alcohol value is still reported by the separate Alcohol Content rule.

Required warnings use a stricter partial-wording score:

- PASS: near-exact required wording and `GOVERNMENT WARNING:` detected in all caps.
- NEEDS REVIEW: most wording appears, heading capitalization is questionable, or warning-specific OCR confidence is below 55%.
- FAIL: missing, materially incomplete, or substantially reworded.

Unlike flexible identity fields, the warning never passes on unordered token presence alone. If skew or layout causes OCR to scramble the sentence but at least 55% of required words and both heading words are detected, the result is NEEDS REVIEW so an agent can confirm exact wording. This avoids both a false FAIL for visibly present text and an unsafe PASS for legally order-sensitive wording.

Physical typography requirements—including the 1 mm, 2 mm, or 3 mm minimum type size, bold heading, non-bold body, continuous-paragraph layout, and maximum characters per inch—cannot be reliably determined from a single digital image without scale metadata. The results therefore show a separate informational NEEDS REVIEW row for image-layout analysis or human review. This row is visible but does not prevent an otherwise valid automated result from receiving PASS.

### Overall Result

- FAIL if any required automated field fails.
- NEEDS REVIEW if there are no failures but at least one required automated field is ambiguous.
- PASS only when all required automated fields pass.
- Conditional beverage-specific fields affect the overall result when an expected value is provided.

## Testing

Install lightweight test dependencies after the application requirements:

```bash
pip install -r requirements-test.txt
pytest
```

The 39 automated tests cover normalization, reordered-token coverage, alcohol/proof and volume parsing, CSV validation, manual per-image data, strict and scrambled-warning behavior, beverage-specific rules and references, overall decision logic, producer/address extraction, error UX, navigation safeguards, themes, image previews, overwritten filtering, filtered-position numbering, export data, and a complete upload-to-results request. HTTP tests disable model startup and inject deterministic OCR output so the suite is fast and repeatable; production uses the real process-wide EasyOCR service. Real EasyOCR checks against the generated Laurel Ridge and Bayview images confirm the observed fragment-order problems that the regressions model.

### Synthetic Test Resources

Twelve generated label images and three matching CSV batches are committed under `tests/resources/sample_data/`. They cover passing spirits, wine, and beer labels; fuzzy matching; missing warnings and origin; ABV and volume mismatches; low contrast; cropping; and skew.

| Test case | Primary behavior exercised | Expected outcome |
| --- | --- | --- |
| `old_tom_distillery.png` | Clean distilled-spirits happy path | PASS |
| `stones_throw_case_variation.png` | Case and punctuation-tolerant fuzzy brand matching | PASS |
| `casa_azul_tequila_import.png` | Imported product with country of origin | PASS |
| `red_ridge_missing_warning.png` | Missing required Government Health Warning | FAIL |
| `north_point_wrong_abv.png` | Numeric alcohol-content mismatch | FAIL |
| `sol_y_mar_missing_country.png` | Imported product without detected origin | FAIL or NEEDS REVIEW, depending on readable context |
| `silver_oak_low_contrast.png` | Low-contrast OCR confidence handling | NEEDS REVIEW |
| `cropped_warning_label.png` | Materially incomplete/cropped warning | FAIL or NEEDS REVIEW |
| `hilltop_wrong_net_contents.png` | Parsed volume mismatch | FAIL |
| `pine_trail_beer.png` | Beer/malt-beverage happy path | PASS |
| `laurel_ridge_wine.png` | Wine path and complete producer-address extraction | PASS |
| `bayview_skewed_angle.png` | Perspective and uneven-lighting tolerance | PASS or NEEDS REVIEW based on OCR confidence |

Regenerate them deterministically without network access:

```bash
python tests/resources/generate_test_data.py
```

See [`tests/resources/sample_data/README.md`](tests/resources/sample_data/README.md) for the scenario matrix and recommended CSV file for each test.

## Security And Data Handling

- Uploaded images and CSV bytes stay in request memory.
- No file writes, database records, object storage, or third-party inference calls occur.
- The code logs processing failures but never full OCR text or application contents.
- Extensions and decoded image formats must both be JPEG or PNG.
- Per-file, total-request, batch-count, and image-pixel limits reduce resource abuse.
- Filenames are reduced to their basename before display or matching.

This prototype has no authentication and should not be exposed as a production system without access controls, rate limiting, malware scanning, hardened headers, and agency privacy/security review.

## Assumptions And Tradeoffs

- Application values are treated as the expected source of truth.
- Manual values are keyed to each uploaded filename; adding or removing a thumbnail adds or removes its matching field section without clearing data entered for the remaining images.
- OCR is expected-value-guided to produce useful explanations without pretending to infer an entire COLA application.
- The adaptive second OCR pass balances imperfect-image handling against the five-second-per-label usability target.
- Processing is synchronous for transparent prototype behavior. Large enterprise batches should use background jobs.
- Local OCR is less semantically flexible than an LLM, but is reproducible, offline-capable, inspectable, and free of evaluator credentials.
- The app does not integrate with COLA.

## Known Limitations

- Blur, glare, severe perspective skew, curved bottles, and stylized type can reduce OCR accuracy.
- Physical type size, bold weight, continuous-paragraph layout, contrast, and character density cannot be established from pixels alone without scale metadata and layout analysis.
- PDF submissions are out of scope.
- The implemented beverage-specific fields are conditional expected-text checks, not a complete wine, beer, spirits, formula, or disclosure rules engine.
- There is no authentication, persistent audit record, human annotation, or live COLA connection.
- A synchronous 200–300 image batch may take significant time and may exceed a reverse-proxy request timeout.
- OCR confidence is a useful signal, not a calibrated probability of regulatory correctness.

## Future Improvements

1. Add a durable job queue and progress screen for enterprise batches.
2. Detect label panels and rectify perspective before OCR.
3. Expand beverage-specific rule packs with TTB counsel review and versioned citations.
4. Add persistent agent notes, user identity, and auditable review history.
5. Add optional, agency-hosted ambiguous-case review behind a feature flag.
6. Integrate approved identity, malware scanning, retention controls, and COLA APIs.
7. Benchmark representative label sets and tune thresholds against human-reviewed outcomes.

## Project Structure

```text
app/
  main.py                    FastAPI routes and orchestration
  config.py                  limits and required warning
  models.py                  typed request/result models
  image_service.py           validation and preprocessing
  ocr_service.py             process-wide EasyOCR adapter
  csv_service.py             batch application parsing
  manual_service.py          filename-keyed manual application parsing
  extraction_service.py      expected-guided field extraction
  verification_service.py    deterministic field and overall rules
  normalizer.py              text, ABV/proof, and volume normalization
  warning_validator.py       strict federal warning check
  templates/                 Jinja pages
  static/                    local Bootstrap, CSS, and interaction JS
tests/                       focused unit and request-flow coverage
  resources/                 deterministic generator and synthetic label/CSV fixtures
Dockerfile                   CPU OCR production image
render.yaml                  Render Blueprint
```
