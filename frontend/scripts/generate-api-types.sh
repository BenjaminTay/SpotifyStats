#!/bin/bash
# Generate TypeScript types from the running backend's OpenAPI spec.
# Requires the backend to be running at http://localhost:8000.
set -euo pipefail

SPEC_URL="${1:-http://localhost:8000/openapi.json}"
OUTPUT="src/api/generated/api-types.ts"
SNAPSHOT="src/api/generated/openapi.json"

echo "Fetching OpenAPI spec from $SPEC_URL ..."
curl --noproxy "*" -sf "$SPEC_URL" -o "$SNAPSHOT"
npx openapi-typescript "$SNAPSHOT" -o "$OUTPUT"
echo "Done → $OUTPUT"
