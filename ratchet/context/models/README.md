# models/ — Mechanism 2 state

This directory holds the self-tuning cheapest-rung table and its raw outcome log.
Mechanism 2 plugs in at the per-step model-dispatch decision inside `implement`:
read the rung table to pick the starting rung for the step's task class, run the
step, append the outcome, then re-tune so the next dispatch starts at the cheapest
rung with a demonstrated pass rate at or above threshold.

JSON cannot hold comments, so both file formats are documented here.

## rung-table.json

One object per task class: the cheapest provider/model whose measured pass rate
is at or above threshold. Fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `task_class` | string | kind of step the rung serves (e.g. `mechanical_edit`, `test_writing`, `refactor`) |
| `provider` | string | provider name (e.g. `openai-codex`) |
| `model` | string | model name on that provider (e.g. `gpt-5.6-luna`) |
| `attempts` | int | number of recorded step outcomes for this task class on this model |
| `passes` | int | number of those outcomes that passed |
| `total_cost_usd` | number | summed cost of those attempts, USD |
| `total_latency_s` | number | summed latency of those attempts, seconds |
| `last_updated` | string | ISO 8601 timestamp of the last tuning write |

Derived fields — computed, never stored, because JSON cannot compute them:

- `pass_rate = passes / attempts`
- `avg_cost_usd = total_cost_usd / attempts`

The table is a tuned projection of `outcomes.log.jsonl`, not an independent
record: its `attempts` count is the number of matching outcomes in the log.

## outcomes.log.jsonl

Append-only log: one JSON object per line, one line per completed step dispatch.
Each line has exactly these fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `task_class` | string | task class of the step (matches rung-table) |
| `provider` | string | provider used for the step |
| `model` | string | model used for the step |
| `result` | string | `pass` or `fail` |
| `cost_usd` | number | cost of the step, USD |
| `latency_s` | number | wall time of the step, seconds |
| `ts` | string | ISO 8601 timestamp of the outcome |

Example line (also valid JSON on its own):

    {"task_class": "mechanical_edit", "provider": "openai-codex", "model": "gpt-5.6-luna", "result": "pass", "cost_usd": 0.035, "latency_s": 26.5, "ts": "2026-08-16T06:54:00Z"}

The file starts empty and only grows; tuning recomputes the rung table from it
rather than rewriting history.
