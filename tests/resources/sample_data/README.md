# Synthetic TTB test resources

These labels are generated assets for prototype testing only. They do not use real brands,
logos, applications, or regulatory approvals.

Regenerate every image and CSV from the repository root:

```bash
python tests/resources/generate_test_data.py
```

## Scenarios

| Label | Purpose | Expected outcome | Suggested CSV |
| --- | --- | --- | --- |
| `old_tom_distillery.png` | Complete bourbon label | PASS | `sample_labels.csv` |
| `stones_throw_case_variation.png` | Case and punctuation variation | Brand PASS | `sample_labels.csv` |
| `casa_azul_tequila_import.png` | Imported tequila with origin | PASS | `sample_labels.csv` |
| `red_ridge_missing_warning.png` | Missing statutory warning | FAIL warning | `failing_labels.csv` |
| `north_point_wrong_abv.png` | Label 40% vs application 45% | FAIL alcohol | `failing_labels.csv` |
| `sol_y_mar_missing_country.png` | Imported label without origin | FAIL/NEEDS REVIEW country | `failing_labels.csv` |
| `silver_oak_low_contrast.png` | Low-contrast wine artwork | NEEDS REVIEW likely | `batch_mixed.csv` |
| `cropped_warning_label.png` | Warning cut off at bottom | FAIL/NEEDS REVIEW warning | `batch_mixed.csv` |
| `hilltop_wrong_net_contents.png` | Label 1 L vs application 750 mL | FAIL net contents | `failing_labels.csv` |
| `pine_trail_beer.png` | Complete beer label | PASS | `sample_labels.csv` |
| `laurel_ridge_wine.png` | Complete wine label | PASS | `sample_labels.csv` |
| `bayview_skewed_angle.png` | Angled label and uneven lighting | PASS/NEEDS REVIEW | `batch_mixed.csv` |

## CSV sets

- `sample_labels.csv`: mostly passing labels for a clean demonstration.
- `failing_labels.csv`: missing or mismatched compliance data.
- `batch_mixed.csv`: passing, failing, and OCR-challenging labels together.

The CSVs intentionally use the original take-home schema. The application continues to
accept that schema for compatibility in addition to the simplified UI sample format.
