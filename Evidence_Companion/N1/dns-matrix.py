import json
import os
import subprocess
import time
from pathlib import Path

out = Path(os.environ["N1_DIR"]) / "dns-matrix"
out.mkdir()
context = subprocess.check_output(
    ["kubectl", "config", "current-context"], text=True).strip()
if not context.startswith("gke_") or not context.endswith("_paper-lab"):
    raise SystemExit("Expected paper-lab GKE context.")

def k(*args):
    return subprocess.check_output(
        ["kubectl", "--context", context, *args],
        text=True, stderr=subprocess.PIPE, timeout=30)

for ns in ("n1-edge", "n1-untrusted"):
    policies = json.loads(k("-n", ns, "get", "networkpolicy", "-o", "json"))
    if policies["items"]:
        raise SystemExit("Expected the completed HTTP test to restore empty policies.")

dns = json.loads(k("-n", "kube-system", "get", "svc", "kube-dns", "-o", "json"))
resolver = dns["spec"]["clusterIP"]
target = json.loads(k("-n", "n1-serving", "get", "svc", "inference", "-o", "json"))
expected_ip = target["spec"]["clusterIP"]

probe = r'''
import json, secrets, socket, struct, sys
transport, resolver, expected = sys.argv[1:]
name = "inference.n1-serving.svc.cluster.local"
qid = secrets.randbits(16)
question = b"".join(bytes([len(s)]) + s.encode() for s in name.split("."))
question += b"\0" + struct.pack("!HH", 1, 1)
query = struct.pack("!6H", qid, 0x0100, 1, 0, 0, 0) + question

def exact(sock, size):
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ValueError("short reply")
        data += chunk
    return data

def skip_name(data, offset):
    while True:
        size = data[offset]
        offset += 1
        if size == 0:
            return offset
        if size & 0xc0 == 0xc0:
            return offset + 1
        if size > 63:
            raise ValueError("invalid label")
        offset += size

try:
    kind = socket.SOCK_DGRAM if transport == "UDP" else socket.SOCK_STREAM
    with socket.socket(socket.AF_INET, kind) as sock:
        sock.settimeout(2)
        sock.connect((resolver, 53))
        if transport == "UDP":
            sock.send(query)
            data = sock.recv(4096)
        else:
            sock.sendall(struct.pack("!H", len(query)) + query)
            size = struct.unpack("!H", exact(sock, 2))[0]
            data = exact(sock, size)
    rid, flags, questions, answers, _, _ = struct.unpack_from("!6H", data)
    valid = (rid == qid and flags & 0x820f == 0x8000 and questions == 1
             and data[12:12 + len(question)] == question)
    offset = 12 + len(question)
    addresses = []
    for _ in range(answers):
        offset = skip_name(data, offset)
        typ, cls, ttl, size = struct.unpack_from("!HHIH", data, offset)
        offset += 10
        if typ == 1 and cls == 1 and size == 4:
            addresses.append(socket.inet_ntoa(data[offset:offset + size]))
        offset += size
    result = {"result": "allow" if valid and addresses == [expected]
              else "wrong-answer", "addresses": addresses}
except TimeoutError:
    result = {"result": "timeout"}
except Exception as exc:
    result = {"result": "error", "error": type(exc).__name__}
print(json.dumps(result))
'''

(out / "probe.py").write_text(probe)
(out / "environment.json").write_text(json.dumps({
    "resolver": resolver, "expected_service_ip": expected_ip,
    "fqdn": "inference.n1-serving.svc.cluster.local"
}, indent=2))

def sample(ns, pod, transport):
    return json.loads(k("-n", ns, "exec", pod, "--",
                        "python", "-c", probe, transport, resolver, expected_ip))

def document(name, rules):
    return {
        "apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy",
        "metadata": {"name": name, "namespace": "n1-edge"},
        "spec": {"podSelector": {}, "policyTypes": ["Egress"], "egress": rules}
    }

deny = document("dns-test-deny", [])
allow = document("dns-test-allow", [])
peer = {
    "namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kube-system"}},
    "podSelector": {"matchExpressions": [{
        "key": "k8s-app", "operator": "In",
        "values": ["kube-dns", "node-local-dns"]
    }]}
}
deny_path = out / "deny.json"
deny_path.write_text(json.dumps(deny, indent=2))
allow_exists = False
stages = [
    ("baseline", None, True, True),
    ("deny", [], False, False),
    ("udp-only", ["UDP"], True, False),
    ("tcp-only", ["TCP"], False, True),
    ("both", ["UDP", "TCP"], True, True),
    ("remove-allow", [], False, False),
    ("restore-baseline", None, True, True)
]
summary = []

for index, (label, protocols, udp, tcp) in enumerate(stages):
    if index == 1:
        k("apply", "--dry-run=server", "--validate=strict", "-f", str(deny_path))
        k("apply", "-f", str(deny_path))
    if protocols:
        allow["spec"]["egress"] = [{
            "to": [peer], "ports": [{"port": 53, "protocol": p} for p in protocols]
        }]
        path = out / f"{label}-policy.json"
        path.write_text(json.dumps(allow, indent=2))
        k("apply", "--dry-run=server", "--validate=strict", "-f", str(path))
        k("apply", "-f", str(path))
        allow_exists = True
    elif allow_exists:
        k("-n", "n1-edge", "delete", "networkpolicy", "dns-test-allow")
        allow_exists = False
    if label == "restore-baseline":
        k("-n", "n1-edge", "delete", "networkpolicy", "dns-test-deny")

    records = []
    for transport, permitted in [("UDP", udp), ("TCP", tcp)]:
        expected = "allow" if permitted else "timeout"
        attempts = []
        consecutive = 0
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline and consecutive < 3:
            observation = sample("n1-edge", "frontend", transport)
            attempts.append(observation)
            consecutive = consecutive + 1 if observation["result"] == expected else 0
            if consecutive < 3:
                time.sleep(1)
        control = sample("n1-untrusted", "client", transport)
        records.append({
            "transport": transport, "expected": expected,
            "attempts": attempts, "health_control": control,
            "matched": consecutive == 3 and control["result"] == "allow"
        })
    result = {
        "stage": label,
        "outcome": "PASS" if all(r["matched"] for r in records) else "CHECK_REQUIRED",
        "observations": records
    }
    (out / f"{label}.json").write_text(json.dumps(result, indent=2))
    summary.append({"stage": label, "outcome": result["outcome"]})
    print(label, result["outcome"], flush=True)
    if result["outcome"] != "PASS":
        break

report = {
    "outcome": "PASS" if len(summary) == len(stages)
               and all(s["outcome"] == "PASS" for s in summary) else "CHECK_REQUIRED",
    "stages": summary
}
(out / "result.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
print("Evidence saved in", out)
