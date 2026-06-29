# Synthetic TTB test resources

These 50 labels are deterministic test assets only. They use fictional brands, generated
logos, and synthetic application data; they are not regulatory approvals.

Regenerate every image and the three CSV batches from the repository root:

```bash
python tests/resources/generate_test_data.py
```

## Coverage

- Distilled spirits: 18
- Wine / sake: 16
- Beer / malt beverage: 16
- Physical/camera variants include torn, rotated, blurred, dirty, zoomed, cropped,
  mirrored, upside-down, low-resolution, glare, shadow, perspective, water damage,
  occlusion, dense logos, curved-container shading, and unconventional text placement.

## Scenarios

| Label | Category | Purpose | Expected routing | CSV |
| --- | --- | --- | --- | --- |
| `old_tom_distillery.png` | Distilled spirits | clean control artwork | PASS or OCR-dependent review | `sample_labels.csv` |
| `stones_throw_case_variation.png` | Distilled spirits | decorative shapes and punctuation variation | PASS or OCR-dependent review | `sample_labels.csv` |
| `casa_azul_tequila_import.png` | Distilled spirits | imported product with dense logo artwork | PASS or OCR-dependent review | `sample_labels.csv` |
| `red_ridge_missing_warning.png` | Distilled spirits | missing statutory warning | FAIL or NEEDS REVIEW | `failing_labels.csv` |
| `north_point_wrong_abv.png` | Distilled spirits | prominent logo with an application alcohol mismatch | FAIL or NEEDS REVIEW | `failing_labels.csv` |
| `sol_y_mar_missing_country.png` | Distilled spirits | imported product missing country-of-origin text | FAIL or NEEDS REVIEW | `failing_labels.csv` |
| `silver_oak_low_contrast.png` | Wine / sake | low contrast with slight blur | Mixed OCR/rule outcome | `batch_mixed.csv` |
| `cropped_warning_label.png` | Wine / sake | bottom crop removes part of the warning | FAIL or NEEDS REVIEW | `failing_labels.csv` |
| `hilltop_wrong_net_contents.png` | Distilled spirits | application and label net contents disagree | FAIL or NEEDS REVIEW | `failing_labels.csv` |
| `pine_trail_beer.png` | Beer / malt beverage | clean beer control with landscape logo | PASS or OCR-dependent review | `sample_labels.csv` |
| `laurel_ridge_wine.png` | Wine / sake | clean wine control with vintage | PASS or OCR-dependent review | `sample_labels.csv` |
| `bayview_skewed_angle.png` | Distilled spirits | seven-degree rotation with uneven shadow | Mixed OCR/rule outcome | `batch_mixed.csv` |
| `ember_cask_torn_bourbon.png` | Distilled spirits | multiple torn-away label sections | FAIL or NEEDS REVIEW | `failing_labels.csv` |
| `midnight_vodka_blurry.png` | Distilled spirits | strong Gaussian focus blur | FAIL or NEEDS REVIEW | `failing_labels.csv` |
| `copper_fox_rotated_left.png` | Distilled spirits | thirteen-degree counterclockwise rotation | PASS or OCR-dependent review | `sample_labels.csv` |
| `atlas_gin_zoomed_out.png` | Distilled spirits | small distant label surrounded by background | PASS or OCR-dependent review | `sample_labels.csv` |
| `lunar_rum_dirty.png` | Distilled spirits | stains, dirt spots, and vertical scratches | PASS or OCR-dependent review | `sample_labels.csv` |
| `jade_dragon_flipped.png` | Distilled spirits | mirrored label photograph | FAIL or NEEDS REVIEW | `failing_labels.csv` |
| `crooked_still_weird_layout.png` | Distilled spirits | off-center brand and diagonally placed product text | Mixed OCR/rule outcome | `batch_mixed.csv` |
| `prairie_moon_glare.png` | Distilled spirits | strong diagonal reflective glare | Mixed OCR/rule outcome | `batch_mixed.csv` |
| `black_anchor_cropped_side.png` | Distilled spirits | side crop removes portions of multiple lines | FAIL or NEEDS REVIEW | `failing_labels.csv` |
| `summit_brandy_perspective.png` | Distilled spirits | trapezoidal camera perspective distortion | FAIL or NEEDS REVIEW | `failing_labels.csv` |
| `frost_line_upside_down.png` | Wine / sake | 180-degree inverted photograph | FAIL or NEEDS REVIEW | `failing_labels.csv` |
| `wild_rose_water_stain.png` | Wine / sake | large translucent water rings | PASS or OCR-dependent review | `sample_labels.csv` |
| `canyon_echo_zoomed_in.png` | Wine / sake | tight crop enlarged beyond the label edges | Mixed OCR/rule outcome | `batch_mixed.csv` |
| `blue_door_vertical_text.png` | Wine / sake | brand printed vertically beside normal text | Mixed OCR/rule outcome | `batch_mixed.csv` |
| `orchard_lane_low_resolution.png` | Wine / sake | severe downsample and pixelated upscale | PASS or OCR-dependent review | `sample_labels.csv` |
| `granite_peak_shadow.png` | Wine / sake | deep directional shadow across half the label | PASS or OCR-dependent review | `sample_labels.csv` |
| `paper_crane_logo_heavy.png` | Wine / sake | oversized geometric logo competing with text | Mixed OCR/rule outcome | `batch_mixed.csv` |
| `mossy_bank_crumpled.png` | Wine / sake | paper folds, highlights, and crease shadows | PASS or OCR-dependent review | `sample_labels.csv` |
| `sunroom_overexposed.png` | Wine / sake | washed-out highlights and reduced contrast | Mixed OCR/rule outcome | `batch_mixed.csv` |
| `broken_compass_cropped_top.png` | Wine / sake | top crop removes category and logo context | FAIL or NEEDS REVIEW | `failing_labels.csv` |
| `night_jar_dark.png` | Wine / sake | underexposed dark label with weak contrast | FAIL or NEEDS REVIEW | `failing_labels.csv` |
| `riverbend_noisy.png` | Wine / sake | dense salt-and-pepper camera noise | Mixed OCR/rule outcome | `batch_mixed.csv` |
| `golden_hour_occluded.png` | Wine / sake | opaque tape covers warning text | FAIL or NEEDS REVIEW | `failing_labels.csv` |
| `iron_hop_rotated_right.png` | Beer / malt beverage | eleven-degree clockwise rotation | PASS or OCR-dependent review | `sample_labels.csv` |
| `cloudline_motion_blur.png` | Beer / malt beverage | horizontal camera-motion blur | PASS or OCR-dependent review | `sample_labels.csv` |
| `tiny_ale_zoomed_out.png` | Beer / malt beverage | small distant label surrounded by background | Mixed OCR/rule outcome | `batch_mixed.csv` |
| `festival_lager_weird_layout.png` | Beer / malt beverage | off-center brand and diagonally placed product text | Mixed OCR/rule outcome | `batch_mixed.csv` |
| `brickhouse_dirty.png` | Beer / malt beverage | stains, dirt spots, and vertical scratches | PASS or OCR-dependent review | `sample_labels.csv` |
| `neon_stag_glare.png` | Beer / malt beverage | strong diagonal reflective glare | Mixed OCR/rule outcome | `batch_mixed.csv` |
| `coastal_pilsner_perspective.png` | Beer / malt beverage | trapezoidal camera perspective distortion | PASS or OCR-dependent review | `sample_labels.csv` |
| `upside_down_stout.png` | Beer / malt beverage | 180-degree inverted photograph | FAIL or NEEDS REVIEW | `failing_labels.csv` |
| `torn_ticket_saison.png` | Beer / malt beverage | multiple torn-away label sections | Mixed OCR/rule outcome | `batch_mixed.csv` |
| `pixel_porter_low_resolution.png` | Beer / malt beverage | severe downsample and pixelated upscale | Mixed OCR/rule outcome | `batch_mixed.csv` |
| `sidecrop_amber.png` | Beer / malt beverage | side crop removes portions of multiple lines | Mixed OCR/rule outcome | `batch_mixed.csv` |
| `mirror_ipa_flipped.png` | Beer / malt beverage | mirrored label photograph | Mixed OCR/rule outcome | `batch_mixed.csv` |
| `curved_can_pale_ale.png` | Beer / malt beverage | simulated cylindrical can-edge shading | PASS or OCR-dependent review | `sample_labels.csv` |
| `mudtrack_brown_ale.png` | Beer / malt beverage | heavy mud splatter and scratches | PASS or OCR-dependent review | `sample_labels.csv` |
| `half_label_wheat_cropped.png` | Beer / malt beverage | lower half and statutory warning removed | FAIL or NEEDS REVIEW | `failing_labels.csv` |

## CSV sets

- `sample_labels.csv`: 18 clean-to-moderate examples across categories.
- `failing_labels.csv`: 16 compliance failures and severe OCR cases.
- `batch_mixed.csv`: all 50 images for full-batch evaluation.

The CSVs retain the original take-home schema for compatibility. Image distortion may
cause OCR-dependent routing even when the synthetic application row matches the artwork.
