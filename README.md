# Kubernetes security and resilience practitioner study

This repository companion supports the practitioner paper **Security and Resilience for Kubernetes Infrastructure Supporting AI/ML Workloads: A Practitioner Framework with Bounded GKE Validation**, by Michael Ifeanyi. Its six-control framework is supported by selected observations from one GKE cluster using synthetic workloads and a separate fictional inventory exercise.

Read and cite the published paper: https://doi.org/10.5281/zenodo.24486098

## Evidence

Paths below are relative to the `Evidence_Companion/` directory in this repository. The companion's own README explains redactions, original and derivative checksums, limitations, and reuse. The source records describe the original execution; redacted copies have not been rerun as packaged.

| Case | Locations | Scope |
|---|---|---|
| A1 | `A1/allow.json`, `A1/deny.json`, `A1/schema-negative.json` and corresponding logs | Server-side admission dry-run comparisons |
| I1 | `I1/result.json`, `I1/token-on-effective.json`, `I1/token-off-effective.json` | Token projection and file-presence observations in running Pods |
| N1 | `N1/http-matrix/`, `N1/dns-matrix/` and their Python harnesses | Selected HTTP and DNS comparisons |
| R1 | `R1/evidence/`, `R1/checkpoints/`, `R1/gke_r1/`, `R1/follow-up/` | Deterministic CPU checkpoint recovery after a controlled process exit |
| V1 | `V1/` | Fictional vulnerability-inventory exercise |

The original DNS deny-policy manifest was overwritten by the deny-stage result. Its policy definition remains in the original harness. `N1/corrected/dns-matrix.py` changes the output filename and was syntax-checked, with no new GKE run. DNS backend identity was not established. The HTTP and DNS probes are repeated observations in one cluster, not independent replications. Checkpoint recovery used one surviving worker and volume.

Manuscript YAML excerpts are illustrative. The evidence companion contains redacted derivatives of recorded fixtures, and its corrected DNS harness is syntax-validated only. No sandbox-runtime, cloud authorization, protected-endpoint, GPU, production-inference, node-loss, or storage-loss test was performed.

## Integrity and use

`Evidence_Companion/SHA256SUMS.json` lists checksums of packaged files. `Transformation_Inventory.json` records original and derivative hashes for transformed text records. Checkpoint bytes are retained unchanged. The companion is a reviewable collection of methods and observations, not a turnkey runner. Review the harnesses and adapt them to a separate authorized cluster before attempting any new experiment.

## Start here

Read the paper, then examine the [checkpoint verification log](Evidence_Companion/R1/evidence/verify.jsonl) and [checksums](Evidence_Companion/SHA256SUMS.json). The [companion README](Evidence_Companion/README.md) documents evidence status and redactions.


## License

The [MIT License](LICENSE) applies only to the original Python scripts
authored by Michael Ifeanyi in `Evidence_Companion/`. It does not cover
evidence logs, captured outputs, checkpoint files, redacted records,
or third-party material.

The [Zenodo paper](https://doi.org/10.5281/zenodo.24486098) is licensed
separately under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
