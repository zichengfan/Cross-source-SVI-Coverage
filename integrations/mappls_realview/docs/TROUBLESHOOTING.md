# SDK workflow troubleshooting

## Wrong Python environment

Use the shared interpreter:

```text
cross_source_svi_coverage/.venv/bin/python
```

In Jupyter select `cross-source-svi-coverage (.venv)`.

## Playwright Sync API inside asyncio

Notebook calls must use:

```python
manifest = await capture_sdk_bbox_async(...)
```

The synchronous `capture_sdk_bbox()` entrypoint is for CLI/non-async callers.

## SDK fails to load

Confirm the static key, local origin whitelist and network access. The local
page is normally served from `http://127.0.0.1:8765`.

## RealView source is not detected

If the base map loads but `realviewSourceDetected` remains false, confirm that
RealView is enabled for the same Mappls project.

## Captured tile count is zero or incomplete

- keep the bbox small and use a validated zoom;
- increase the per-tile wait time;
- confirm the SDK still emits the expected RealView request marker;
- treat missing cells as capture uncertainty until retried.

Failed cells and their HTTP status are stored in the production run summary.
A missing GeoJSON file alone must not be interpreted as no coverage.

## PBF decoder fails

The service has previously labelled valid MVT bodies as `image/webp`. Validate
the body with the MVT decoder rather than relying only on Content-Type.
Use `debug` mode when the raw PBF and full schema are needed for diagnosis.

## Geometry is mirrored or misplaced

The validated transform uses `y_coord_down=True` and canonical XYZ. Compare a
fresh sample with roads in QGIS before scaling after any SDK or decoder change.

Historical HAR/cURL replay troubleshooting is archived under `docs/legacy/`.
