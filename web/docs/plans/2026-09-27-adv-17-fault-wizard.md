# ADV-17 Fault Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let operators select and preview a model outage, track its derived snapshot, and enter a comparison with baseline direction preserved.

**Architecture:** A dedicated React route reuses the existing snapshot candidate query and ADV-16 fault endpoint. It freezes one submission and idempotency key, polls the job and candidate snapshot, and offers a comparison link only after both report ready. The comparison page validates URL preselection against loaded snapshots and keeps its explicit analysis forms.

**Tech Stack:** React, TypeScript, Ant Design, TanStack Query, Vitest, Playwright.

**Spec:** `web/docs/changeloge/advance/adv-17-fault-simulation-ui.md`

## Global Constraints

- Show model-only wording and preserve baseline/candidate direction.
- No direct SDK or engine endpoint from the browser; submit through registered API routes.
- Do not launch comparison or reachability analysis automatically.
- Keep status, warning and error information visible at the summary level in both themes.

## Review Focus

- Double click while POST is pending: exactly one candidate is registered.
- Selecting a whole node after one of its interfaces: remove the redundant interface target.
- Network or baseline change: old task and candidate cannot appear as current context.
- Failed/interrupted/unknown task or non-ready snapshot: no completed-state link.
- URL preselection from a stale or other-network snapshot: do not create a reversed or invalid comparison.

### Task 1: Fault draft and preview

**Files:** `src/features/faults/FaultsPage.tsx`, `src/features/faults/faults.test.tsx`, `src/app/App.tsx`, `src/app/style.css`.

**Interfaces:** `/faults` route; selected baseline; deduplicated node and `{node,interface}` targets; typed request matching `FaultScenarioRequest`.

- [x] Write failing tests for target choice, de-duplication and preview.
- [x] Implement the smallest form using `useSnapshots` and `useCandidates`, then run the tests.

### Task 2: Submit and track

**Files:** `src/features/faults/FaultsPage.tsx`, `src/features/faults/faults.test.tsx`.

**Interfaces:** POST fault-scenarios with frozen body/idempotency key; GET job and snapshot; visible failure/unknown diagnosis and success link.

- [x] Write failing double-click, failure/unknown and ready-gate tests.
- [x] Implement submission lock, query polling and ready-only comparison link, then run tests.

### Task 3: Fixed handoff and acceptance

**Files:** `src/features/changes/ChangesPage.tsx`, `src/features/faults/faults.test.tsx`, `tests/faults.spec.ts`, spec/index/evidence documents.

**Interfaces:** `/changes?baseline=<id>&candidate=<id>` preselection only when both ready snapshots belong to the selected network.

- [x] Write failing handoff/direction and scope-confirmation tests.
- [x] Implement URL preselection and real-browser flow over synthetic Cisco configs.
- [x] Run cumulative frontend, backend, smoke, browser, HTTPS recovery and dual-theme checks.
- [x] Review, record evidence and commit ADV-17 after all required checks pass.
