# Naver Panorama Frontend Investigation

Date: 2026-05-20

## Conclusion

The Naver web frontend does expose a panorama/street-view coverage layer that can be fetched from the browser-facing tile stack.

The coverage is not exposed as a clean vector/MVT source in the sampled frontend path. The useful source is a raster overlay tile family:

- `https://map.pstatic.net/nrb/styles/basic/{version}/{z}/{x}/{y}.png?mt=bg.ol.ts.pr.lko`

The matching picker endpoint also loads:

- `https://map.pstatic.net/nrb/picker/basic/{version}/{z}/{x}/{y}.json?mt=ts.pr.lko&crs=EPSG:4326`

But the sampled picker tiles were structurally identical to the base `mt=ts.lko` picker tiles and only contained ordinary POI features. In other words, the picker JSON was not the useful coverage payload in the sampled session.

## Evidence Chain

1. The page opened in mini panorama mode and exposed `거리뷰 / 항공뷰 / 수중뷰` controls in the map UI.
2. The main frontend bundle contains panorama-specific logic:
   - `/api/panorama/nearby`
   - `/api/place/panorama/${t}`
   - a rendered-layer query against `M.PANORAMA.toUpperCase()`
3. A probe run on the live frontend captured these resource families:
   - base picker: `mt=ts.lko`
   - panorama picker: `mt=ts.pr.lko`
   - base style PNG: `mt=bg.ol.ts.lko`
   - panorama style PNG: `mt=bg.ol.ts.pr.lko`
   - panorama viewer assets from `panorama.map.naver.com` and `panorama.pstatic.net`
4. A paired tile comparison showed:
   - `mt=ts.pr.lko` picker JSON == `mt=ts.lko` picker JSON for the sampled tile
   - `mt=bg.ol.ts.pr.lko` PNG != `mt=bg.ol.ts.lko` PNG for the sampled tile
   - the `pr` PNG visibly contains blue road-following lines consistent with panorama coverage

## Version Discovery

The raster version is discoverable from the public style JSONP:

- `https://map.pstatic.net/nrb/styles/basic.json?fmt=png&callback=__naver_maps_callback__0`

Sample response snippet:

```json
{
  "version": "1778829614",
  "tiles": [
    "https://map.pstatic.net/nrb/styles/basic/1778829614/{z}/{x}/{y}.png"
  ]
}
```

That same `version` can be reused to build the panorama overlay and picker URLs above.

## Practical Takeaway

For extraction aligned with `0001_extract_coverage_layers_raw.ipynb`, Naver currently looks most viable as a raster coverage source, not as a vector source:

- fetch `bg.ol.ts.pr.lko` PNG tiles over a tile range
- treat the overlay as the coverage layer to analyze
- optionally fetch `ts.pr.lko` picker JSON for click interaction parity, but do not rely on it for coverage geometry unless later samples prove otherwise
