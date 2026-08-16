# Findings ledger

Findings are durable, numbered observations from `check` and `audit`. The ledger
is append-only except for status transitions — IDs are never reused or renumbered.

## Format

One finding per line, exactly:

    F-<NN> [<P0|P1|P2>] <open|fixed|closed>: <description>

- `F-<NN>` — durable ID, never reused or renumbered.
- Priority: `P0` (blocking, must fix), `P1` (should fix), `P2` (nice to fix).
- Status lifecycle: `open` → `fixed` → `closed`. A finding moves to `closed`
  ONLY via re-review (the fix is verified) or an explicit accept-with-reason.
  Nothing else closes a finding.

## Examples (one per status)

F-01 [P1] open: contract hash sidecar is never re-verified at the complete gate
F-02 [P0] fixed: implement can start without an approved contract; fix verified by re-review, awaiting accept
F-03 [P2] closed: plan.md checkbox format was ambiguous; accepted with reason "format now documented in plan.md itself"

## Open findings

<PLACEHOLDER: the live open/fixed list is maintained here as the item proceeds.
On `complete`, the gate requires no open or fixed P0/P1 findings.>
