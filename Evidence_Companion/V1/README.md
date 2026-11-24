# V1 fictional advisory tabletop

**Result: PASS, 22 November 2026 at 21:11:08 UTC.** The exercise kept the case open after a tag change and after an incomplete rollout. It closed the fictional record once both affected serving replicas showed the fixed platform image. A separate SQLite comparison of all twelve inventory entries reproduced the counts.

## Decision record

| Stage | Evidence and decision |
|---|---|
| Intake | Opened V1-FICTION-001 against a synthetic two-replica serving application. The advisory, component names and build inventory were authored for this exercise. |
| Validation | The fictional advisory specifies fixture-reader 1.0 as affected and 1.1 as fixed. The build inventory links those versions to separate image indexes and linux/arm64 manifests A and B. Manifest C contains fixture-metrics and falls outside the stated advisory. The digest strings are synthetic identifiers. |
| Classification | Prioritize replacement before closing the case because both serving instances show the affected version. The fixture supplies no severity score or evidence of exploitability. |
| Affectedness | Reconciled the three in-scope instance identities against each snapshot. Evaluate each deployed platform digest against the build inventory. Use the desired tag and image index to identify rollout discrepancies. |
| Ownership | Fictional image owner is responsible for replacement. The action is due before the exercise closure checkpoint. The fictional vulnerability coordinator adjudicates closure. These are simulated assignments. |
| Remediation | Select B for both serving replicas. A tag change with A still deployed leaves the case open. If the replacement is incomplete, retain the open case and reconcile the remaining replica. Returning to A also reopens the case. |
| Verification | The verifier checked each desired index and corresponding inventory, the deployed platform manifests, package and version, the unaffected comparator, and the expected residual instances. The secondary check evaluated platform/digest joins directly against the source CSVs. |
| Closure | On the complete-rollout fixture, both serving replicas map to B; the collector maps to C. Record the simulated decision as remediated and closed at the exercise timestamp. Follow-up assigned to the fictional coordinator: use the same per-instance inventory reconciliation before closing the next tabletop case. |

| Snapshot | Affected | Fixed | Unaffected comparator | Decision |
|---|---:|---:|---:|---|
| Before change | 2 | 0 | 1 | Open |
| Changed tag | 2 | 0 | 1 | Open |
| Partial rollout | 1 | 1 | 1 | Open; serving/replica-2 still runs A |
| Complete rollout | 0 | 2 | 1 | Remediated and closed |

## Reproduce and inspect

Run `python3 verify_tabletop.py` from this directory. The script reads the source files relative to its own path and emits a timestamped JSON result on standard output. The retained run exited with status 0. Its hashes cover the three input files and the verifier. The offline fixture requires Python 3; it uses only the standard library. Raw inputs are `advisory.json`, `build_inventory.csv` and `deployed_inventory.csv`. The retained observations are in `result.json`. The separate verification query, its result and counts are in `independent_check.json`.

The test exercised the decision sequence on generated data. The secondary check independently computed the disposition counts from the same fixtures; both checks were performed in the same session. No real organization, vulnerability, software image, rollout or response time was observed.
