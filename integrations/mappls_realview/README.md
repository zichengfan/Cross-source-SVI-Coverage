# Mappls RealView integration

This integration contains the authorization-gated Web Maps SDK workflow used
to capture and decode Mappls RealView coverage vectors. It is intentionally
separate from the anonymous provider registry.

Copy `web/config.example.js` to the ignored `web/config.local.js` and populate
the key manually. Never commit the populated file, browser profiles, captures,
HAR files, signed URLs or raw credentials.

```bash
python -m pip install -e '.[dev]'
pytest
python scripts/capture_sdk_bbox.py --help
```

The legacy HAR replay pipeline and historical request samples are deliberately
excluded from the shared repository. Production use requires an authorized
Mappls key and compliance with the applicable agreement.
