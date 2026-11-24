# Evidence companion

This redacted evidence companion provides supporting records for the practitioner paper. It is not a turnkey reproducibility package. Original author-supplied archives remain separate and unchanged. No new GKE tests were executed during packaging.

## Evidence locators

| Case | Relative location | Evidence scope |
|---|---|---|
| A1 | A1/allow.json, deny.json, schema-negative.json; corresponding logs and exit-codes.txt | Original server dry-run decisions, with infrastructure metadata redacted where present |
| I1 | I1/result.json; token-on-effective.json; token-off-effective.json | Effective token projection and file-existence observations |
| N1 HTTP | N1/http-matrix/; N1/http-matrix.py | Thirteen stages, four paths, repeated observations and listener correlation |
| N1 DNS | N1/dns-matrix/; N1/dns-matrix.py | Seven protocol stages; historical filename-collision limitation remains |
| N1 corrected | N1/corrected/dns-matrix.py | Corrected deny-policy output path; Python parsing only, no GKE rerun |
| R1 | R1/evidence/; R1/gke_r1/; R1/follow-up/; R1/checkpoints/ | Controlled interruption and recovery on a surviving worker and PVC; six unchanged checkpoint files |
| V1 | V1/ | Fictional advisory and deployment inventory; offline checker and recorded observations |

## Redaction and integrity

Project identifiers, worker names, user-home account names, infrastructure IPv4 addresses and UUIDs have deterministic substitutes. Equality relationships are retained across files. UUID substitution includes any matching correlation identifiers consistently. Loopback and wildcard IPv4 addresses are retained. Substituted addresses are documentation values, not a deployable network. Cluster CA text, if present, is omitted. Original image digests, source version labels, checkpoint bytes, timestamps and scientific results are retained.

Transformation_Inventory.json records each text file's original and derivative digest and whether its text changed. Historical checksums embedded in records refer to ORIGINAL files, not transformed copies. SHA256SUMS.json records this companion's current file hashes. Do not compare a sanitized manifest against an original manifest hash and describe the expected mismatch as tampering.

## Configuration status and reuse

Original supplied A1/I1/N1/R1 executions are tested only within the manuscript's stated scope. Redacted copies are derivatives, not newly executed configurations. Python sources are parser-checked only during release preparation; JSON files are parsed for structural readability, not Kubernetes API schema validation. V1 is a fictional offline exercise. The two manuscript YAML fragments remain illustrative.

Before any future live execution, create a separate authorized disposable cluster, replace documentation addresses and worker placeholders from observed cluster state, review namespace labels and policy peers, pin image and policy versions, and record positive controls. Inspect each harness's arguments and source. A1/I1/N1 setup and evidence are not packaged as a single certified runner. R1 source includes a runner but its redacted version has not been executed. Keep original and future-run evidence separate. No cloud resources should be created merely to read or audit this package.

A repeat study should preserve effective objects before each transition, separate DNS policy and result filenames, add combined named HTTP checks, and explicitly select any expanded failure boundary. Such work is future validation, not part of the reported baseline.
