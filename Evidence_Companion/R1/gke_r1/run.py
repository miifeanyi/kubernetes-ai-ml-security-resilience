"""Create R1 fixtures once in the disposable paper-cpu cluster."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from assess import CODES, assess, reference_hash, require

ROOT = Path(__file__).resolve().parent
NAMESPACE = "paper-r1"
NODE = os.environ["R1_NODE"]
CONTEXT = os.environ["R1_CONTEXT"]
IMAGE = "python@sha256:b685a4fa58bb19d1814d78a1ec0f0208f351452724f78b20212c984d6e124a34"
SA = "training-sa"
PVC = "r1-state"
FIXTURES = "r1-fixtures"
HASH = "r1-reference-hash"


def stamp():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def obj(kind, name, **fields):
    api = "batch/v1" if kind == "Job" else "v1"
    meta = {"name": name}
    if kind != "Namespace":
        meta["namespace"] = NAMESPACE
    return {"apiVersion": api, "kind": kind, "metadata": meta, **fields}


def job(stage):
    commands = {"reference": ["train.py", "fresh", "--dir", "/state/reference"],
                "interrupt": ["train.py", "fresh", "--dir", "/state/interrupted", "--exit-after-update", "6"],
                "resume": ["train.py", "resume", "--dir", "/state/interrupted"],
                "verify": ["verify.py", "/state/reference/step-0012.json", "/state/interrupted/step-0012.json"],
                "bad-copy": ["train.py", "resume", "--dir", "/state/empty-negative"]}
    script, *args = commands[stage]
    if script == "train.py":
        args += ["--steps", "12", "--save-every", "4"]
    security = {"runAsNonRoot": True, "runAsUser": 10001, "runAsGroup": 10001, "fsGroup": 10001,
                "seccompProfile": {"type": "RuntimeDefault"}}
    container = {
        "name": "fixture", "image": IMAGE, "imagePullPolicy": "IfNotPresent",
        "command": ["python", "-B", "/lab/" + script, *args],
        "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True,
                            "capabilities": {"drop": ["ALL"]}},
        "volumeMounts": [{"name": "code", "mountPath": "/lab", "readOnly": True},
                         {"name": "state", "mountPath": "/state", "readOnly": stage == "verify"}],
    }
    if stage in ("resume", "bad-copy"):
        container["env"] = [{"name": "EXPECTED_H4", "valueFrom": {
            "configMapKeyRef": {"name": HASH, "key": "expected-h4"}}}]
    pod = {"serviceAccountName": SA, "automountServiceAccountToken": False,
           "securityContext": security, "nodeSelector": {"kubernetes.io/hostname": NODE},
           "restartPolicy": "Never", "containers": [container],
           "volumes": [{"name": "code", "configMap": {"name": FIXTURES}},
                       {"name": "state", "persistentVolumeClaim": {"claimName": PVC,
                                                                    "readOnly": stage == "verify"}}]}
    return obj("Job", "r1-" + stage, spec={"parallelism": 1, "completions": 1, "backoffLimit": 0,
                                          "activeDeadlineSeconds": 600, "template": {"spec": pod}})


def fixtures():
    namespace = obj("Namespace", NAMESPACE)
    namespace["metadata"]["labels"] = {"pod-security.kubernetes.io/enforce": "restricted",
                                       "pod-security.kubernetes.io/enforce-version": "v1.36"}
    yield namespace
    yield obj("ServiceAccount", SA, automountServiceAccountToken=False)
    yield obj("ConfigMap", FIXTURES, immutable=True, data={
        name: (ROOT / name).read_text() for name in ["train.py", "verify.py"]})
    yield obj("PersistentVolumeClaim", PVC, spec={
        "volumeMode": "Filesystem", "accessModes": ["ReadWriteOnce"], "storageClassName": "standard-rwo",
        "resources": {"requests": {"storage": "1Gi"}}})
    for stage in CODES:
        yield job(stage)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--render-only", action="store_true")
    args = parser.parse_args()
    directory = args.evidence.resolve()
    directory.mkdir(exist_ok=True, parents=True)
    require(not any(directory.iterdir()), "R1 output directory must be empty")
    rendered = directory / "manifests"
    rendered.mkdir()
    statuses = []
    calls = []

    def save_fixture(item):
        location = rendered / (item["metadata"]["name"] + ".json")
        write(location, item)
        return location

    def k(*argv):
        result = subprocess.run(["kubectl", "--context", CONTEXT, "--request-timeout=800s", *argv],
                                capture_output=True, text=True, timeout=810)
        safe_args = [arg.replace(str(directory) + "/", "") for arg in argv]
        calls.append({"args": safe_args, "exit_code": result.returncode})
        if result.returncode:
            print(result.stderr, file=sys.stderr)
            raise RuntimeError(f"kubectl {argv[0]} exit {result.returncode}")
        return result.stdout

    def create(location):
        k("create", "--dry-run=server", "--validate=strict", "-f", str(location))
        k("create", "--validate=strict", "-f", str(location))

    def get(kind, *more):
        return json.loads(k("-n", NAMESPACE, "get", kind, *more, "-o", "json"))

    items = list(fixtures())
    paths = [save_fixture(item) for item in items]
    if args.render_only:
        return
    require(bool(os.environ.get("KUBECONFIG")), "use the coordinating runner's isolated kubeconfig")
    require(CONTEXT.startswith("gke_") and CONTEXT.endswith("_paper-lab"),
            "Expected GKE paper-lab context")
    started = stamp()
    summary = {"scope": "Kubernetes Job/Pod replacement on one worker with one surviving GKE Persistent Disk PVC",
               "started_utc": started, "run_id": "R1-GKE-" + started[:19].replace("-", "").replace(":", "") + "Z",
               "outcome": "inconclusive"}
    try:
        storage = get("storageclass", "standard-rwo")
        summary["storage"] = {key: storage.get(key) for key in ["provisioner", "volumeBindingMode"]}
        require(storage.get("provisioner") == "pd.csi.storage.gke.io", "Expected PD CSI")
        require(storage.get("volumeBindingMode") == "WaitForFirstConsumer", "Unexpected binding mode")
        summary["server_version"] = json.loads(k("version", "-o", "json"))["serverVersion"]["gitVersion"]
        require(summary["server_version"].startswith("v1.36."), "Expected Kubernetes 1.36")
        node = json.loads(k("get", "node", NODE, "-o", "json"))
        require(any(c["type"] == "Ready" and c["status"] == "True"
                    for c in node["status"]["conditions"]), "Worker is not Ready")
        existing = k("get", "namespace", NAMESPACE, "--ignore-not-found", "-o", "json").strip()
        require(not existing, "paper-r1 already exists; preserve previous evidence and inspect before retrying")
        create(paths[0])
        summary["namespace"] = "created with Restricted/v1.36 labels"
        for path in paths[1:4]:
            create(path)
        codes = {}
        for stage in CODES:
            if stage == "resume":
                create(save_fixture(obj("ConfigMap", HASH, immutable=True,
                                        data={"expected-h4": reference_hash(directory)})))
            name = "r1-" + stage
            create(rendered / (name + ".json"))
            condition = "complete" if CODES[stage] == 0 else "failed"
            k("-n", NAMESPACE, "wait", "job/" + name, "--for=condition=" + condition, "--timeout=720s")
            (pod,) = get("pods", "-l", "job-name=" + name)["items"]
            volume = next(v["persistentVolumeClaim"] for v in pod["spec"]["volumes"] if v["name"] == "state")
            claim = get("pvc", volume["claimName"])
            require(claim["status"]["phase"] == "Bound", "PVC unavailable")
            state = pod["status"]["containerStatuses"][0]
            terminated = state["state"]["terminated"]
            entry = {"stage": stage, "pod_uid": pod["metadata"]["uid"],
                     "node": pod["spec"]["nodeName"], "pvc_uid": claim["metadata"]["uid"],
                     "pv_name": claim["spec"]["volumeName"], "image_id": state["imageID"],
                     "claim_read_only": volume.get("readOnly", False), "restarts": state["restartCount"],
                     "reason": terminated["reason"], "exit_code": terminated["exitCode"]}
            statuses.append(entry)
            (directory / (stage + ".jsonl")).write_text(
                k("-n", NAMESPACE, "logs", "pod/" + pod["metadata"]["name"], "-c", "fixture"))
            codes[stage] = entry["exit_code"]
            print(f"{stage}: exit={codes[stage]} expected={CODES[stage]}", flush=True)
            require(entry["node"] == NODE and entry["restarts"] == 0, "unexpected placement or restart")
            require(codes[stage] == CODES[stage], f"unexpected exit code for {stage}")
            require(entry["claim_read_only"] == (stage == "verify"), "unexpected PVC mount mode")
        require(len({p["pod_uid"] for p in statuses}) == len(CODES), "expected distinct Pods")
        for key in ["pvc_uid", "pv_name", "image_id"]:
            require(len({p[key] for p in statuses}) == 1, f"inconsistent {key}")
        summary.update(assess(directory, codes))
    except (Exception, KeyboardInterrupt) as exc:
        summary["error"] = str(exc)
        raise
    finally:
        summary.update(ended_utc=stamp(), placements=statuses,
                       manifests_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                         for p in sorted(rendered.glob("*.json"))})
        write(directory / "result.json", summary)
        write(directory / "commands.json", calls)


if __name__ == "__main__":
    main()
