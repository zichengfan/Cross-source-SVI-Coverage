# Acquisition notebooks

This folder contains operational examples for the shareable acquisition layer,
not scientific analysis from the parent project.

- `0001_provider_acquisition_smoke_cases.ipynb` exercises offline planning for
  all 14 registry providers and documents guarded calls for Tencent PMTiles and
  Mappls RealView, bringing the total to 16 provider paths.

The notebook defaults to no network access. Enable a guarded acquisition cell
only after checking authorization, credentials, rate limits, target extent and
output location.
