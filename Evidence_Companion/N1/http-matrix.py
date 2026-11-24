import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

out = Path(os.environ["N1_DIR"])
targets = json.loads((out / "targets.json").read_text())
context = subprocess.check_output(
    ["kubectl", "config", "current-context"], text=True).strip()
if not context.startswith("gke_") or not context.endswith("_paper-lab"):
    raise SystemExit("Expected paper-lab GKE context.")

def k(*args):
    return subprocess.check_output(
        ["kubectl", "--context", context, *args],
        text=True, stderr=subprocess.PIPE, timeout=45)

probe = r'''
import http.client, json, sys, uuid
rid = uuid.uuid4().hex
c = http.client.HTTPConnection(sys.argv[1], 8080, timeout=2)
try:
    c.request("GET", "/", headers={"X-Lab-Request": rid, "Connection": "close"})
    r = c.getresponse()
    good = (r.status == 200 and r.read() == b"lab-inference-ok\n"
            and r.getheader("X-Lab-Request") == rid)
    result = {"result": "allow" if good else "wrong-response",
              "request_id": rid}
except TimeoutError:
    result = {"result": "timeout", "request_id": rid}
except Exception as e:
    result = {"result": "error", "error": type(e).__name__, "request_id": rid}
finally:
    c.close()
print(json.dumps(result))
'''

def observe(ns, pod, address):
    return json.loads(k("-n", ns, "exec", pod, "--",
                        "python", "-c", probe, address))

def peer(ns, role):
    return {
        "namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": ns}},
        "podSelector": {"matchLabels": {"role": role}}
    }

def policy(ns, name, direction, other=None):
    spec = {"podSelector": {}, "policyTypes": [direction]}
    if other:
        field = "to" if direction == "Egress" else "from"
        spec[direction.lower()] = [{
            field: [other], "ports": [{"protocol": "TCP", "port": 8080}]
        }]
    return {
        "apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy",
        "metadata": {"namespace": ns, "name": name}, "spec": spec
    }

policies = {}
for ns in ("n1-edge", "n1-untrusted", "n1-serving"):
    doc = policy(ns, "deny-all", "Ingress")
    doc["spec"]["policyTypes"] = ["Ingress", "Egress"]
    policies[ns] = doc

policies["edge-out"] = policy(
    "n1-edge", "edge-out", "Egress", peer("n1-serving", "inference"))
policies["edge-in"] = policy(
    "n1-serving", "edge-in", "Ingress", peer("n1-edge", "frontend"))
policies["client-out"] = policy(
    "n1-untrusted", "client-out", "Egress", peer("n1-serving", "inference"))
policies["client-in"] = policy(
    "n1-serving", "client-in", "Ingress", peer("n1-untrusted", "frontend"))

folder = out / "http-matrix"
folder.mkdir()
for key, doc in policies.items():
    (folder / f"{key}.json").write_text(json.dumps(doc, indent=2))

stages = [
    ("baseline", [], True, True),
    ("default-deny", ["+n1-edge", "+n1-untrusted", "+n1-serving"], False, False),
    ("egress-only", ["+edge-out"], False, False),
    ("ingress-only", ["-edge-out", "+edge-in"], False, False),
    ("both", ["+edge-out"], True, False),
    ("remove-egress", ["-edge-out"], False, False),
    ("restore-egress", ["+edge-out"], True, False),
    ("remove-ingress", ["-edge-in"], False, False),
    ("restore-ingress", ["+edge-in"], True, False),
    ("untrusted-egress", ["+client-out"], True, False),
    ("untrusted-admitted", ["+client-in"], True, True),
    ("untrusted-blocked-again", ["-client-in"], True, False),
    ("restore-baseline",
     ["-client-out", "-edge-out", "-edge-in",
      "-n1-edge", "-n1-untrusted", "-n1-serving"], True, True),
]

def topology():
    records = {}
    for ns, pod in [("n1-edge", "frontend"), ("n1-untrusted", "client"),
                    ("n1-serving", "inference")]:
        obj = json.loads(k("-n", ns, "get", "pod", pod, "-o", "json"))
        status = obj["status"]
        if not any(c["type"] == "Ready" and c["status"] == "True"
                   for c in status.get("conditions", [])):
            raise RuntimeError(f"{ns}/{pod} is not Ready")
        records[ns] = {
            "uid": obj["metadata"]["uid"], "ip": status["podIP"],
            "node": obj["spec"]["nodeName"],
            "restarts": [s["restartCount"] for s in status["containerStatuses"]]
        }
    return records

baseline = topology()
summary = []
for label, changes, edge_allowed, client_allowed in stages:
    for change in changes:
        path = str(folder / f"{change[1:]}.json")
        if change[0] == "+":
            k("apply", "--dry-run=server", "--validate=strict", "-f", path)
            k("apply", "-f", path)
        else:
            k("delete", "-f", path)

    record = {"stage": label, "started_utc": datetime.now(timezone.utc).isoformat(),
              "cases": [], "outcome": "PASS"}
    for ns, pod, allowed in [
        ("n1-edge", "frontend", edge_allowed),
        ("n1-untrusted", "client", client_allowed)
    ]:
        for target, address in targets.items():
            expected = "allow" if allowed else "timeout"
            attempts = []
            consecutive = 0
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline and consecutive < 3:
                item = observe(ns, pod, address)
                attempts.append(item)
                consecutive = consecutive + 1 if item["result"] == expected else 0
                if consecutive < 3:
                    time.sleep(1)
            matched = consecutive == 3
            record["cases"].append({
                "source": ns, "target": target, "expected": expected,
                "matched": matched, "attempts": attempts})
            if not matched:
                record["outcome"] = "CHECK_REQUIRED"

    record["listener_control"] = observe("n1-serving", "inference", "127.0.0.1")
    record["topology_stable"] = topology() == baseline
    if record["listener_control"]["result"] != "allow" or not record["topology_stable"]:
        record["outcome"] = "CHECK_REQUIRED"
    (folder / f"{label}.json").write_text(json.dumps(record, indent=2))
    summary.append({"stage": label, "outcome": record["outcome"]})
    print(label, record["outcome"], flush=True)
    if record["outcome"] != "PASS":
        break

logs = k("-n", "n1-serving", "logs", "inference")
(folder / "listener.log").write_text(logs)
seen = {json.loads(line)["request_id"] for line in logs.splitlines() if line}
expected_ids = set()
for stage in summary:
    record = json.loads((folder / f"{stage['stage']}.json").read_text())
    for case in record["cases"]:
        expected_ids.update(a["request_id"] for a in case["attempts"]
                            if a["result"] == "allow")
missing = sorted(expected_ids - seen)
result = {
    "outcome": "PASS" if len(summary) == len(stages)
               and all(s["outcome"] == "PASS" for s in summary)
               and not missing else "CHECK_REQUIRED",
    "stages": summary, "missing_listener_request_ids": missing,
    "scope": "HTTP Pod-IP and Service-IP network-policy comparisons"
}
(folder / "result.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
print("Evidence saved in", folder)
