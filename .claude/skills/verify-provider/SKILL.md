---
name: verify-provider
description: Run the standard pilot-fetch and quality checks for a finished street-view provider and report pass/fail. Use after a provider module is implemented and before merging its PR.
---

# verify-provider

Run the standard verification sequence for one provider in the Cross-Source SVI
Coverage project, then report a pass/fail summary.

For a thorough independent review, delegate to the **provider-verifier**
subagent. Use this skill directly for a quick check.

## Steps

1. **Tests & lint**
   ```
   uv run pytest
   uv run ruff check src/ tests/
   ```
   The provider's own unit tests must exist and pass.

2. **Registration**
   ```
   uv run coverage-acquisition list-providers
   ```
   `<key>` must appear.

3. **Pilot fetch** — use the pilot bbox from `docs/providers/<key>.md`:
   ```
   uv run coverage-acquisition fetch-provider --provider <key> \
     --bbox <min_lon> <min_lat> <max_lon> <max_lat> \
     --output-root data/raw --continue-on-error
   ```
   The manifest must report tiles fetched, decoded, and non-empty coverage.

4. **Rasterize** the pilot output to a z14 COG (see the `rasterize-coverage`
   skill); confirm the COG is valid, EPSG:3857, `uint8`, covered pixels > 0.

5. **Plausibility** — coverage must fall on land/roads for the pilot city, not
   ocean or blank space.

## Output
Each step PASS/FAIL with evidence, then an overall verdict. On failure, list
precise, actionable defects.
