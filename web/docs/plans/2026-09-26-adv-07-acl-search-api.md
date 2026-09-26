# ADV-07 ACL Search API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose bounded ACL witness search and rule reachability through the existing job/result APIs without treating absence of evidence as a safety proof.

**Architecture:** The API validates separate typed requests and submits jobs through `AnalysisService`. The registry records cost and SDK question identities; controller functions map only approved parameters to public Pybatfish questions. Structured results retain raw SDK evidence and add narrowly worded warnings.

**Tech Stack:** FastAPI, Pydantic, Pybatfish `2026.9.17.3748`, PostgreSQL jobs, pytest, generated OpenAPI TypeScript.

**Spec:** [ADV-07](../changeloge/advance/adv-07-acl-search-api.md)

## Global Constraints

- Fixed engine revision `7d0deeeac4a09973b3876327f6aef721ee12f955` and SDK `2026.9.17.3748`.
- `api → service → controller → Pybatfish`; cross-module access through services.
- Require explicit node and filter scope; reject arbitrary engine context and SDK kwargs.
- Preserve SDK cause and blocking lines; never infer safety from an empty witness set.

## Review Focus

- Empty search returns uncertainty, not allow/deny or global safety.
- Empty-condition and shadowed rule remain distinguishable.
- Match-line action cannot omit its line number or inject SDK syntax.
- Selector scope cannot silently become all devices or all filters.
- Unsupported Huawei/H3C ACL interpretation is rejected before queueing.

### Task 1: Typed contracts and fixed SDK mappings

**Files:** `web/backend/app/modules/analysis/schemas/filters.py`, `controllers/filters.py`, `registry.py`, `api.py`, `service.py`, `controller.py`, `web/backend/tests/test_filter_search.py`.

- [x] Add contract/mapping tests; run targeted pytest and observe expected missing-capability failure.
- [x] Implement scoped requests, approved headers/action mapping, registry entries, endpoints, model guard, and evidence-preserving warnings.
- [x] Run targeted tests green and review layer boundaries.

### Task 2: Real SDK acceptance and cumulative regression

**Files:** `web/backend/tests/test_filter_search.py`, capability expectation tests, generated `web/frontend/src/api/schema.d.ts`.

- [x] Add real SDK witness, shadowed/empty, and no-witness tests; verify against the fixed engine.
- [x] Run target and full backend against the fixed lab; regenerate OpenAPI types.
- [x] Run cumulative smoke, frontend, browser, deployment, light/dark acceptance, lint and contract gates.
- [x] Record evidence and update spec/index/matrix; review the deliverable for ADV-07 submission.
