# Operator runbooks

One procedure per `ErrorCategory`, so an alert deep-links to the recovery
procedure. Each runbook states the detection signal, mitigation commands, and
the escalation path. `qwen-web-arwaky doctor` prints `docs/runbooks/` when a
check fails, and `deploy/sentry-alerts.yaml` names the matching file on every
alert rule.

The mapping from category to file lives in
`modules/shared/src/utility_core_env.py::runbook_index` and is echoed by
`qwen-web-arwaky doctor --json` under `runbooks`.

| Category | Runbook |
| --- | --- |
| `auth` | [auth-expiry.md](auth-expiry.md) |
| `browser` | [browser-launch.md](browser-launch.md) |
| `disk` / `file_io` | [disk-exhaustion.md](disk-exhaustion.md) |
| `session` | [session-corruption.md](session-corruption.md) |
| `update` | [update-failure.md](update-failure.md) |
| `network` | [network.md](network.md) |
| `rate_limit` | [rate-limit.md](rate-limit.md) |
| `response_timeout` | [response-timeout.md](response-timeout.md) |
| `stuck` | [stuck.md](stuck.md) |
| `injection` | [injection.md](injection.md) |
| `parsing` | [parsing.md](parsing.md) |
| `model` | [model-switch.md](model-switch.md) |
| `other` | [other.md](other.md) |

## First moves during an incident

```bash
qwen-web-arwaky doctor            # which check failed, and what it says to do
qwen-web-arwaky doctor --json     # same, plus masked env, capacity, runbook index
jq . ~/.local/state/qwen-web-arwaky/log/status.json
jq -r 'select(.category != null)' ~/.local/state/qwen-web-arwaky/log/app.jsonl | tail -50
```

`status.json` carries `schema_version`, `updated_at`, the last run's status, and
the rolling-24h execution metrics, so a monitor can poll one file. `doctor`
reports `file_only` telemetry as a WARNING on a production host; provision
`SENTRY_DSN` (see `.env.example`) before relying on the Sentry alerts, otherwise
a failing host produces no external signal at all.
