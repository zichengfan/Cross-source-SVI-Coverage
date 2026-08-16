# Acquisition notebooks

This folder contains operational examples for the shareable acquisition layer,
not scientific analysis from the parent project.

- `0001_provider_acquisition_smoke_cases.ipynb` compares providers over shared
  case-study bounds and displays each XYZ provider from z10 through z18 over
  the same projected 1 km × 1 km square around its existing validated centre;
  Kakao instead follows its reversed native scale from L10 through L2. It
  covers all 14 registry providers plus Tencent PMTiles and Mappls RealView.
  Validated same-area and fixed-extent maps are embedded, so they remain visible
  without the excluded raw acquisition data. Access-gated or unsupported levels
  remain explicit status panels rather than implied coverage absence.
- `build_0001_provider_comparison_cases.py` regenerates the notebook structure
  without copying local data or credentials. Regeneration intentionally clears
  cell outputs; execute the reference-build workflow before publishing a new
  notebook snapshot.

The notebook defaults to no network access. Enable a guarded acquisition cell
only after checking authorization, credentials, rate limits, target extent and
output location. The fixed-extent reference workflow processes one provider and
one zoom at a time, draws at most 50,000 deterministically sampled symbols for
dense vector sources, and deletes each raw run directory immediately after
rendering. It is a visual comparison only and does not calculate accuracy,
coverage or cost scores.
