# Rule documentation

This document records the regulatory guidance basis used by the TTB Alcohol Label Pre-Screener. The prototype provides decision support only; it does not replace the regulations, TTB guidance, COLA review, or agent judgment.

## Official TTB references

| Beverage or rule | Source |
| --- | --- |
| Beer / Malt Beverage | [TTB Malt Beverage Labeling](https://www.ttb.gov/regulated-commodities/beverage-alcohol/beer/labeling) |
| Distilled Spirits | [TTB Distilled Spirits Labeling](https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/labeling) |
| Wine | [TTB Wine Labeling](https://www.ttb.gov/regulated-commodities/beverage-alcohol/wine/labeling) |
| Beer / Malt Beverage Health Warning | [TTB Malt Beverage Health Warning](https://www.ttb.gov/regulated-commodities/beverage-alcohol/beer/labeling/malt-beverage-health-warning) |
| Distilled Spirits Health Warning | [TTB Distilled Spirits Health Warning](https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/ds-labeling-home/ds-health-warning) |
| Wine Health Warning | [TTB Wine Health Warning](https://www.ttb.gov/regulated-commodities/beverage-alcohol/wine/labeling-wine/wine-labeling-health-warning-statement) |

## Beverage source selection

For manual entry, the user explicitly selects beer or malt beverage, distilled spirits, or wine for each uploaded filename. CSV rows may provide the same `beverage_type`; otherwise the application infers it from class/type text. Common and beverage-specific results then link to the corresponding TTB labeling guidance page. If a legacy CSV row cannot be classified reliably, the result retains its requirement basis and states that the source depends on beverage classification rather than guessing a source.

Government Health Warning results use the beverage-specific TTB health-warning page. The statutory warning rule is common across covered beverage types, while the displayed source follows the classified product type.

## Implemented field rules

| Field | Prototype rule | Source mapping |
| --- | --- | --- |
| Brand name | Normalized fuzzy comparison against application data; case, punctuation, and spacing alone do not fail. | Beverage-specific TTB labeling page |
| Class / type | Normalized fuzzy comparison against the submitted beverage designation. | Beverage-specific TTB labeling page |
| Alcohol content | Parses ABV and proof statements and compares numeric values and units. | Beverage-specific TTB labeling page |
| Net contents | Parses supported metric quantities and compares normalized milliliters. | Beverage-specific TTB labeling page |
| Bottler / producer | Fuzzy comparison for producer, bottler, or importer name and address. | Beverage-specific TTB labeling page |
| Country of origin | Checked when the application marks or infers the product as imported. | Beverage-specific TTB labeling page |
| Government Health Warning | Required at 0.5% ABV or above; checks near-verbatim wording, all-caps heading, and warning-specific OCR confidence. | Beverage-specific TTB health-warning page |
| Warning typography and physical size | Always routed to informational NEEDS REVIEW when the warning is required because physical scale, boldness, paragraph structure, and character density cannot be established reliably from a single image. | Beverage-specific TTB health-warning page |
| Beer / malt beverage special disclosure | When an expected value is supplied, compares an applicable sulfite, aspartame, color-additive, or similar statement against OCR text. | TTB Malt Beverage Labeling |
| Wine appellation of origin | When an expected value is supplied, compares the appellation against OCR text. Applicability depends on the wine's other label claims and context. | TTB Wine Labeling |
| Wine sulfite declaration | When an expected value is supplied, compares the declaration against OCR text; TTB guidance identifies the 10 ppm sulfur-dioxide threshold. | TTB Wine Labeling |
| Distilled spirits age statement | When an expected value is supplied, compares it against OCR text. Applicability varies by spirits class and circumstances. | TTB Distilled Spirits Labeling |
| Distilled spirits commodity statement | When an expected value is supplied, compares the submitted composition or commodity wording against OCR text. | TTB Distilled Spirits Labeling |

## Result source fields

Every field result exposes:

- `requirement_basis`: plain-language reason for the check;
- `source_name`: human-readable TTB source label;
- `source_url`: official TTB guidance URL, when the beverage type can be classified.

The results page displays this information alongside expected text, detected text, status, and explanation so an agent can trace each automated conclusion to its implementation reference.

## Limitations

The linked TTB pages are implementation references, not a complete encoding of federal regulations. Beverage-specific expected text is checked only when the user supplies it. A blank conditional field is not an automated determination that the requirement is inapplicable. Rules requiring formula data, container measurements, physical samples, geographic context, or other application materials remain manual-review work.
