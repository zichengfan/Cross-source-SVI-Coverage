# Observed request structure

## Coverage module

Observed browser module:

```text
https://sdk.mappls.com/map/sdk/web?realview_v1.js&...&access_token=...
```

## Coverage vector tiles

Observed final network form:

```text
https://apis.mappls.com/advancedmaps/v1/<TOKEN>/base/vector_tile/pbf
    ?b=NaN25
    &x-sec2
    &rg=
    &<dynamic_key>=<base64_payload>
    &t=<signed_token>
```

The Base64 payload decodes to a provider-specific obfuscated string. In the supplied capture, the prefix can be converted back to:

```text
z/x/y
```

and the suffix contains an obfuscated equivalent of:

```text
.pbf?v=realview&x-sec=2
```

Examples recovered from the supplied capture include:

```text
14/11507/7202.pbf?v=realview&x-sec=2
14/11507/7204.pbf?v=realview&x-sec=2
```

The toolkit uses only the observed decoding needed to recover XYZ and detect the RealView marker. It does not attempt to derive `t=`.

## Panorama path

Separate observed request:

```text
pano.mappls.com/mapplsView/getxmlData?...&trip=...&entireTrip=1&street_id=58078...
```

This is treated as panorama/trip metadata rather than the coverage vector tile itself.
