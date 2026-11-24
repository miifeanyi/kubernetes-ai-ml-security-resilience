# GKE R1 recovery test
Status: Python syntax checked and generated JSON parsed. GKE execution pending.
Run in Cloud Shell against the dedicated paper-lab cluster.
Requires R1_NODE and R1_CONTEXT environment variables, and KUBECONFIG.
Run python3 -B run.py NEW_EMPTY_EVIDENCE_DIRECTORY.
Creates the paper-r1 namespace, five Jobs, a 1Gi standard-rwo PVC and ConfigMaps.
Keeps resources and logs for inspection. Capture evidence before deleting paper-r1.
Uses the same training source as the recorded host experiment.
Expected exit codes: reference 0, interrupt 42, resume 0, verify 0, missing checkpoint 41.
Verifies distinct Pod UIDs, same node, PVC UID, PV and image ID, expected exits,
checkpoint hashes and decreasing loss. Verifier mounts the PVC read-only.
Scope is deliberate process termination and replacement Pods with surviving storage.
The script stops on an error. Inspect result.json, Pod status and events before retrying.
Sources:
https://kubernetes.io/docs/concepts/workloads/controllers/job/
https://docs.cloud.google.com/kubernetes-engine/docs/concepts/persistent-volumes
https://kubernetes.io/docs/concepts/security/pod-security-standards/
