# Authorized Web SDK workflow

The supported acquisition path uses a Mappls Web Maps JS static key only to
initialize an authorized local map. The SDK enables RealView and generates its
own signed vector-tile requests. Playwright saves matching response bodies
immediately; it does not forge or replay signing tokens.

```text
web/config.local.js (ignored static key)
        -> local Web Maps JS v3.0 page
        -> map.realview(true)
        -> canonical tile-center traversal
        -> async Playwright response events
        -> temporary PBF body + canonical z/x/y
        -> MVT decode to EPSG:4326
        -> production or debug output
```

## Inputs

- bbox in `west south east north` order, EPSG:4326;
- one XYZ zoom;
- a Web SDK static key whose project has RealView access;
- a local origin allowed by the key's domain/IP restrictions.

## Outputs

Only `production` and `debug` are supported.

`production` writes:

- `production/tiles/{z}/{x}/{y}.geojson.gz`;
- `production/runs/{run_id}.json`, including failed XYZ/status records.

`debug` writes the same production files plus:

- `debug/runs/{run_id}/pbf/{z}/{x}/{y}.pbf`;
- MVT schemas and response diagnostics in `manifest.json`;
- a map screenshot.

Merged/clipped GeoJSON and three XYZ CSV files are not persisted. Production
PBFs are temporary and removed after atomic GeoJSON conversion.

Missing-from-capture is not automatically evidence of no RealView coverage.
Retry missing cells before assigning an uncovered state.

## Notebook and CLI

The notebook uses `await capture_sdk_bbox_async(...)` because Jupyter already
runs an asyncio event loop. The CLI uses the synchronous wrapper, which creates
its own loop outside Jupyter.

Do not place the static key in a notebook, CLI argument, manifest or tracked
HTML file. Only `web/config.example.js` belongs in a source package.
