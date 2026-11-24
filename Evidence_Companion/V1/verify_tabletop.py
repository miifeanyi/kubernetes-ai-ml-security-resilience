"""Verify the bounded, fictional V1 inventory; no external dependencies or network."""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILES = ("advisory.json", "build_inventory.csv", "deployed_inventory.csv", "verify_tabletop.py")
# Independent acceptance oracle from V1: residual affected instances, by scenario.
EXPECTED = {
    "before": {"serving/replica-1", "serving/replica-2"},
    "tag_only": {"serving/replica-1", "serving/replica-2"},
    "partial_rollout": {"serving/replica-2"},
    "complete_rollout": set(),
}


def rows(name):
    with (ROOT / name).open(newline="") as stream:
        return list(csv.DictReader(stream))


def verify():
    advisory = json.loads((ROOT / "advisory.json").read_text())
    builds = rows("build_inventory.csv")
    by_platform = {(row["platform"], row["platform_digest"]): row for row in builds}
    by_index = {(row["platform"], row["index_digest"]): row for row in builds}
    if len(builds) != len(by_index) or len(builds) != len(by_platform):
        raise ValueError("Ambiguous fixture artifact mapping")

    snapshots = defaultdict(list)
    for row in rows("deployed_inventory.csv"):
        snapshots[row["snapshot"]].append(row)
    if set(snapshots) != set(EXPECTED):
        raise ValueError("Missing or unexpected snapshot")

    before_tags = {r["instance"]: r["desired_tag"] for r in snapshots["before"]}
    results = {}
    for name, snapshot in snapshots.items():
        expected_instances = set(advisory["scope"])
        if Counter(row["instance"] for row in snapshot) != Counter(expected_instances):
            raise ValueError(f"{name}: incomplete inventory or duplicate instance")
        affected, fixed, excluded, mapping = [], [], [], {}
        for row in snapshot:
            platform = row["platform"]
            instance = row["instance"]
            if platform != advisory["platform"]:
                raise ValueError(f"{name}: unverified architecture")
            current = by_platform[(platform, row["deployed_platform_digest"])]
            desired = by_index[(platform, row["desired_index_digest"])]
            mapping[instance] = {"desired": desired["artifact"], "deployed": current["artifact"]}
            if advisory["scope"][instance] == "affected_app":
                if name == "tag_only" and row["desired_tag"] == before_tags[instance]:
                    raise ValueError(f"{name}: tag was never changed")
                expected_desired = "B" if name in {"partial_rollout", "complete_rollout"} else "A"
                if desired["artifact"] != expected_desired:
                    raise ValueError(f"{name}: unexpected desired image")
            if current["package"] != advisory["package"]:
                if advisory["scope"][instance] != "unaffected_comparator":
                    raise ValueError(f"{name}: unexpected application replacement")
                excluded.append(instance)
            elif current["version"] == advisory["affected_version"]:
                affected.append(instance)
            elif current["version"] == advisory["fixed_version"]:
                fixed.append(instance)
            else:
                raise ValueError(f"{name}: unsupported package disposition")
        if set(affected) != EXPECTED[name] or set(excluded) != {"monitor/collector-1"}:
            raise ValueError(f"{name}: evidence diverges from the independent acceptance oracle")
        results[name] = {
            "decision": "open" if affected else "remediated_closed",
            "affected": sorted(affected), "verified_fixed": sorted(fixed),
            "excluded": sorted(excluded), "artifact_mapping": mapping,
        }
    return {
        "id": advisory["id"], "label": "Fictional offline tabletop",
        "observed_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "decision_owner": advisory["owner"], "review_role": advisory["reviewer"],
        "fixture_and_checker_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES
        },
        "scenarios": results, "outcome": "PASS",
    }


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
