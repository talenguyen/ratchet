# Project context — <PROJECT NAME>

> Source of truth. Every session reads this file first (right after
> `ratchet/plan.md`). It describes the project the loop is driving, at the level a
> fresh session needs to act without re-asking. Replace the `<PLACEHOLDER>` blocks
> with real content when this project is adopted; keep the section headings.

## Project name

<PLACEHOLDER: e.g. "ratchet-v2" — the working name; the human names it for real>

## One-paragraph description

<PLACEHOLDER: what this project is and what it is for. e.g. "A contract-verified
workflow for driving coding agents: no code until a contract test exists and is
red; no completion unless it is green and untampered; per-step model dispatch
self-tunes to the cheapest rung that demonstrably works.">

## Stack

<PLACEHOLDER: languages, runtimes, test framework, tooling versions. e.g.
"Python 3.12, pytest, no external dependencies; JSON state files under ratchet/".
Fill in for real when the stack is chosen.>

## Key conventions

- <PLACEHOLDER: e.g. "state lives under ratchet/, tool-independent; harness
  adapters are thin pointers only">
- <PLACEHOLDER: e.g. "one active work item at a time — ratchet/context/work-item.md">
- <PLACEHOLDER: any naming, formatting, or process conventions a session must follow>

## Entry points

- `ratchet/plan.md` — the ordered backlog; where a fresh session starts.
- `ratchet/context/work-item.md` — the one active spec.
- `ratchet/context/findings.md` — the findings ledger.
