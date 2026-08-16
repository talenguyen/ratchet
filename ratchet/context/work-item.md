# Work item — <WORK ITEM TITLE>

> Only ONE work-item.md exists at a time: the active spec. `propose` writes it,
> `implement` works through it, and on `complete` it is archived to
> `ratchet/history/{features,fixes,rollbacks}/` (by item type) and this file is
> overwritten by the next item. This is a template — replace the `<PLACEHOLDER>`
> blocks with the real spec; keep the section structure.

Item ID: <PLACEHOLDER: e.g. W-004>
Type: <PLACEHOLDER: feature | fix | rollback>
Status: <PLACEHOLDER: proposed | approved | implementing | checked | audited | complete>

## Goal

<PLACEHOLDER: what this item is for, one short paragraph. The done-when evidence
lives in the contract (Step 0); this is the intent.>

## Step 0: Contract

Mechanism 1 seam. `implement` is blocked until this section is filled and the
contract is approved:

- Contract test file path: <PLACEHOLDER: e.g. ratchet/contracts/W-004/test_contract.py>
- Contract test file sha256: <PLACEHOLDER: recorded by `approve`; `complete`
  re-verifies the on-disk file still matches — see ratchet/contracts/README.md>
- Approval signature: <PLACEHOLDER: recorded by `approve`>

The full contract (test path, sha256, fail-mode evidence, approval signature)
lives in `ratchet/contracts/<work-item-id>/contract.json`.

## Steps

Checkboxes are the state machine: `implement` resumes from the first unchecked
step; do not check a step until its done-when is met.

- [ ] Step 1: <PLACEHOLDER: e.g. write the contract test red — the failing test
  that defines done>
- [ ] Step 2: <PLACEHOLDER: e.g. implement the minimal change that turns it green>
- [ ] Step 3: <PLACEHOLDER: e.g. run the full check and record evidence in the
  findings ledger>
