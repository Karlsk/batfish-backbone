# ADV-08 ACL Advanced UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add separate ACL witness-search and unreachable-rule views with progressive evidence and exact-flow handoff to the existing ACL test.

**Architecture:** The existing `/acl` page becomes a three-tab shell keyed by snapshot. Each new form owns its draft, validates and submits a typed OpenAPI request, and follows the standard job/result flow. Result routing chooses a dedicated view for each operation and loads paged rows through the existing result service; raw evidence remains available in a detail drawer.

**Tech Stack:** React, TypeScript, Ant Design, TanStack Query, Vitest, Playwright.

**Spec:** [ADV-08](../changeloge/advance/adv-08-acl-search-ui.md)

## Global Constraints

- Keep ADV-07 literal node/ACL scope and typed headers/action contract.
- Do not change `web/backend` or infer global safety from empty search/rule rows.
- Bind all submitted jobs and handoff presets to network and snapshot IDs.
- Preserve raw SDK evidence and result truncation/quality warnings.

## Review Focus

- Tab switch keeps the two drafts independent.
- Search-to-test handoff keeps protocol, IPs and ports exactly when supported.
- Empty and partial rows remain unknown rather than green.
- `INDEPENDENTLY_UNMATCHABLE` does not claim a blocking rule.
- Result pages opened from history retain their saved context.

### Task 1: Request builders and forms

**Files:** `web/frontend/src/features/acl/FilterSearch.tsx`, `RuleReachability.tsx`, `advanced-requests.ts`, `acl-advanced.test.tsx`, `FilterTest.tsx`.

- [x] Write failing tests for scoped typed requests, independent form state, validation and witness preset.
- [x] Implement two forms with minimal fields, advanced controls and standard idempotent submission.
- [x] Add three `/acl` tabs and contextual preset handling; run focused tests.

### Task 2: Results and browser acceptance

**Files:** `web/frontend/src/features/acl/AdvancedResults.tsx`, `web/frontend/src/features/results/Results.tsx`, `web/frontend/tests/acl-advanced.spec.ts`.

- [x] Write failing result tests for witness flow, distinct reachability reasons, unknown/partial and raw evidence.
- [x] Implement dedicated result views, details and exact-flow handoff.
- [x] Run real Cisco browser flow and visual check in both themes.
- [x] Run cumulative MVP+ADV-01..08 backend, frontend, browser, HTTPS restore and static gates; record evidence and submit ADV-08.
