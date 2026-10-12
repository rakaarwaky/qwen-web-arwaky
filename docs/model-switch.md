# Operator runbook — Model switch failure (ErrorCategory: model)

**Alerts:** none specific; monitor `category=model`.
**Doctor:** no dedicated check.
**Severity:** warning — the pinned default model is unavailable.

## Detection signals

| Source | Signal |
| --- | --- |
| Log | `ModelSwitchError`, category=model |
| Sentry | category=model accumulates |

## Recovery steps

1. Verify the default model is available:
   ```bash
   echo $QWEN_DEFAULT_MODEL
   ```
2. If the model was retired, update the default in `taxonomy_core_constant.py` and
   redeploy.
3. Retry.

## Prevention

- Monitor Qwen's model catalog for retirements; a deprecation email or changelog
  entry precedes removal.
