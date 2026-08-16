# Acquisition contract

Every acquisition job must identify the provider, endpoint or archive, native
coordinate scheme, requested level, spatial scope, rate policy and output root.
Network jobs should be dry-run first and should write an immutable candidate
inventory before requests begin.

## Required state semantics

- `present`: a successfully decoded payload contains coverage evidence.
- `observed_empty`: a successful response contains no evidence under the
  provider-specific empty rule.
- `unresolved`: the request, capture or decode result is not conclusive.
- `outside_scope`: the tile is outside a documented regional service scope.

An unresolved response must never be treated as negative coverage. Raster
presence must be based on the documented alpha or pixel rule; vector presence
must be based on the expected layer and geometry, not response byte size alone.

## Required provenance

Store request level and native tile coordinates, coordinate scheme, endpoint
identifier, runtime configuration version, response status, response hash,
classification, timestamp and retry history. Credentials, cookies and signed
URLs must not be written to manifests or logs.

## Operational boundary

The package records observed endpoint behaviour. It does not assert that an
endpoint is official, stable or permitted for bulk access. Operators must
confirm authorization, provider terms, rate limits and redistribution rights
before a production run.
