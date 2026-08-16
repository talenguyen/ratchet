# contracts/ — Mechanism 1 state

This directory holds the red-before-green contract for the active work item.
Nothing exists here yet: no real `contract.json` appears until the first real
work item is proposed (per `ratchet/plan.md`).

## Layout

    ratchet/contracts/<work-item-id>/contract.json

One directory per work item, keyed by the item's ID (e.g. `W-004`), containing a
single `contract.json`. Written by `propose`, finalized by `approve`, re-verified
by `complete`.

## contract.json format

| Field | Type | Meaning |
| --- | --- | --- |
| `work_item_id` | string | the item this contract belongs to |
| `test_file_path` | string | path to the contract test file, relative to the project root |
| `test_file_sha256` | string | sha256 of the test file at approval time — the tamper-evident hash sidecar |
| `fail_mode_evidence` | string/object | what the failure looked like at approval time: the red output proving the contract test fails before implementation |
| `approved_by` | string | who approved |
| `approved_at` | string | ISO 8601 timestamp of approval |

## Enforced semantics

- The contract is approvable only when the contract test file exists, is failing
  (red), and its sha256 has been recorded.
- `implement` refuses to start until `contract.json` exists, the recorded sha256
  matches the on-disk test file, and `fail_mode_evidence` is present.
- `complete` recomputes the sha256 and refuses to close the item if it no longer
  matches — a modified test cannot silently pass.
