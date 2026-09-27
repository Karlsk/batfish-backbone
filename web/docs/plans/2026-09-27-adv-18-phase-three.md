# ADV-18 Phase-Three Acceptance Plan

**Goal:** Verify the complete change-and-fault workflow against one pinned Batfish engine while retaining MVP and phase-two behavior.

**Spec:** `web/docs/changeloge/advance/adv-18-phase-three-acceptance.md`

## Scope and checks

- [x] Add a real integration test with one fixed Cisco baseline and a candidate containing known static-route and ACL changes. Assert config line evidence, route add/remove direction and differential reachability against direct public SDK output on the same snapshot pair.
- [x] Fork a fault candidate from the baseline, prove the original snapshot's metadata and SDK node query remain unchanged, and verify a deterministic failed fork never becomes comparable.
- [x] Add one browser acceptance flow that creates/compares the known pair, then forks a model fault and preserves the original baseline on comparison handoff. Keep analysis scope explicit.
- [x] Run the cumulative backend, API smoke, frontend, browser, HTTPS recovery and two-theme/two-user production checks from final source. Confirm prior-stage behavior and no unexpected skips.
- [x] Record counts, engine/SDK versions, synthetic inputs, source fingerprint, model limits and traceable evidence in `web/docs/advance-phase3-acceptance.md`, the spec, indexes and matrix. Commit ADV-18 only after all gates pass.

**Boundaries:** No real devices or Java engine accuracy claims. Use existing isolated lab and owned deployment; no network publishing or merge.
