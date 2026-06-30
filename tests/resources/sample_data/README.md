# Synthetic TTB test resources

These 50 labels are deterministic fixtures that use fictional brands, generated logos, and synthetic application data. They are test inputs, not regulatory approvals or an accuracy benchmark.

Regenerate the images and batch CSV from the repository root:

```bash
python tests/resources/generate_test_data.py
```

## Files

- `labels/`: 50 PNG labels
- `csv/batch_mixed.csv`: application data for all 50 labels

The fixtures cover 18 distilled-spirit labels, 16 wine/sake labels, and 16 beer/malt-beverage labels. Variants include clean controls, deliberate rule mismatches, torn paper, rotation, blur, dirt, glare, shadows, zoom, cropping, mirroring, inversion, perspective, low resolution, occlusion, dense logos, curved-container shading, and unconventional text placement.

## Intended routing

- PASS: 18
- FAIL: 5
- NEEDS REVIEW: 27

See the root [`README.md`](../../../README.md#intended-outcome-reference) for the filename-level reference and the limitations of these expected outcomes. OCR engine, preprocessing, and confidence changes can alter observed results.
