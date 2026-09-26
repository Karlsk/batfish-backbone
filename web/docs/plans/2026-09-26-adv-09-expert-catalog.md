# ADV-09 Expert Catalog Implementation Plan

**Goal:** Expose only registered, enabled analyses through one expert query route and a schema-driven Web form.

**Architecture:** The query API validates its envelope, then calls the existing AnalysisService with the registry ID and exact parameters. Registry models perform the same strict validation as dedicated routes; the existing job/controller/result path is unchanged. Capabilities expose each registered request model's JSON Schema for a generated UI. The UI keeps basic fields and expert options separate, preserves invalid JSON while editing, and shows effective values before submission.

**Spec:** [ADV-09](../changeloge/advance/adv-09-expert-catalog.md)

## Tasks

- [x] Write failing backend tests for dedicated/query equivalence, unknown/disabled IDs, unsafe options and request schema catalog.
- [x] Add typed query route and full request schema to capability DTO, preserving the same service/registry path.
- [x] Write failing frontend tests for schema-generated fields, JSON error preservation and visible effective options.
- [x] Add expert page, capability selection, basic/schema controls and advanced JSON editor with job submission guard.
- [x] Run real Cisco expert query browser flow, r1-r2 cumulative browser flows and backend/frontend/HTTPS restore gates.
- [x] Record evidence and update spec/index/contract; commit ADV-09 separately.
