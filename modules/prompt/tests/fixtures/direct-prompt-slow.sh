#!/usr/bin/env bash
# Pipeline 1 (slow): multi-step reasoning task requiring a longer answer.
cat <<'PROMPT'
Design a REST API for a distributed todo service. Produce:
1) full endpoint table (method, path, request, response schema),
2) error model,
3) authentication scheme,
4) one concrete request/response example per endpoint,
5) openapi 3.0 YAML fragment for one resource only.
PROMPT
