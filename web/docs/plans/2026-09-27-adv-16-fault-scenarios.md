# ADV-16 Fault Scenarios Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create immutable node/interface outage candidates with provenance, quality gating, and safe baseline deletion.

**Architecture:** API validates a small typed request; the changes service validates targets through the analysis service and registers a derived snapshot and durable job under the shared resource lock. The changes controller exclusively calls public `fork_snapshot`; the worker stores initialization diagnostics through the snapshots service. Snapshot deletion checks live derived references under the same lock.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy/PostgreSQL, Pybatfish 2026.9.17.3748, pytest, synthetic Cisco fixtures.

**Spec:** `web/docs/changeloge/advance/adv-16-fault-simulation-api.md`

## Global Constraints

- Preserve `api → service → controller → Pybatfish`; cross-module calls go through public services.
- Never mutate the baseline; use a fresh internal snapshot name and `overwrite=False`.
- Enqueue SDK fork/diagnostics in the independent worker; serialize resource admission and deletion.
- Verify with the fixed local Batfish lab and PostgreSQL, not mocks alone.

## Review Focus

- Unknown node/interface: return 422 before creating a job or snapshot.
- Empty request: reject without SDK work.
- SDK returning no fork name or raising: retained failed job and non-ready snapshot.
- Baseline deletion during/after derived registration: conflict until derived deletion.
- Repeated idempotency key: same snapshot/job, different payload conflicts.

### Task 1: Typed request and target validation

**Files:** `app/modules/changes/schemas.py`, `app/modules/analysis/service.py`, `tests/test_fault_scenarios.py`.

**Interfaces:** `FaultScenarioRequest(display_name, deactivate_nodes, deactivate_interfaces)` and `AnalysisService.fault_targets(actor, network_id, snapshot_id)` returning exact node/interface names.

- [x] Write empty/unknown/valid target tests and observe expected failures.
- [x] Implement typed validation and inventory lookup via the existing analysis controller.
- [x] Run targeted tests and inspect exact 422 fields.

### Task 2: Durable derived snapshot and SDK worker

**Files:** `app/modules/changes/{api,service,controller}.py`, `app/modules/snapshots/{service,repository,schemas}.py`, `app/modules/jobs/{schemas,models}.py`, `app/contracts/dto.py`, `app/composition.py`, `migrations/versions/0010_fault_scenarios.py`, `tests/test_fault_scenarios.py`.

**Interfaces:** `ChangesService.create_fault_scenario(...) -> SnapshotCreated`, `ChangesService.execute_fault_scenario(job)`, `SnapshotsService.create_derived(...)`, `SnapshotsService.complete_derived(...)`; new `fault_scenario` job kind.

- [x] Write baseline immutability, provenance, idempotency, successful fork and failure tests; observe failures.
- [x] Add the migration, snapshot/job contracts, registration, controller and worker handler.
- [x] Run targeted real SDK tests until green; check migration upgrade/downgrade behavior.

### Task 3: Deletion protection and cumulative acceptance

**Files:** `app/modules/lifecycle/service.py`, `app/modules/snapshots/{service,repository}.py`, `tests/test_fault_scenarios.py`, spec/index/evidence documents.

**Interfaces:** `SnapshotsService.require_no_derived(snapshot_id, transaction=tx)`.

- [x] Write deletion and admission-race tests; observe failures.
- [x] Add live-derived reference check under `JobsService.resource_boundary()`.
- [x] Run full backend suite, lab smoke, frontend type/build/tests, relevant browser and HTTPS recovery checks.
- [x] Review changed files and evidence; update spec, indexes, matrix and checkpoint; commit ADV-16 only when all required checks pass.
