"""Acceptance criteria shared by the process and Kubernetes procedures."""
import hashlib
import json
from fractions import Fraction
from pathlib import Path


CODES = {"reference": 0, "interrupt": 42, "resume": 0, "verify": 0, "bad-copy": 41}


def events(directory, name):
    return [json.loads(line) for line in (directory / f"{name}.jsonl").read_text().splitlines()]


def select(rows, event):
    return [row for row in rows if row["event"] == event]


def reference_hash(directory):
    (entry,) = [e for e in events(directory, "reference")
                if e["event"] == "committed" and e["step"] == 4]
    return entry["sha256"]


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def assess(directory, codes):
    require(codes == CODES, f"unexpected process codes: {codes}")
    records = {name: events(directory, name) for name in CODES}
    for name, start, end in [("reference", 1, 12), ("interrupt", 1, 6), ("resume", 5, 12)]:
        updates = [r["step"] for r in select(records[name], "updated")]
        require(updates == list(range(start, end + 1)), f"{name}: update sequence {updates}")
    commits = {name: {r["step"]: r["sha256"] for r in select(records[name], "committed")}
               for name in ("reference", "interrupt", "resume")}
    require(list(commits["reference"]) == [4, 8, 12], "unexpected reference checkpoints")
    require(list(commits["interrupt"]) == [4], "unexpected checkpoint after interruption")
    require(list(commits["resume"]) == [8, 12], "unexpected resume checkpoints")
    (loaded,) = select(records["resume"], "loaded")
    require(loaded["step"] == 4 and loaded["sha256"] ==
            commits["reference"][4] == commits["interrupt"][4], "step-4 hash mismatch")
    (stop,) = select(records["interrupt"], "deliberate_exit")
    require(stop["step"] == 6 and stop["code"] == 42, "unexpected interruption")
    require(records["bad-copy"] == [{"event": "missing_checkpoint", "step": 4}],
            "missing-checkpoint test did not stop before training")
    (check,) = records["verify"]
    require(check["event"] == "compared" and check["matches"]
            and check["reference"]["step"] == check["resumed"]["step"] == 12
            and check["reference"]["sha256"] == check["resumed"]["sha256"] ==
            commits["reference"][12] == commits["resume"][12], "final comparison failed")
    require(commits["reference"][8] == commits["resume"][8], "replayed step-8 differs")
    (initial,) = select(records["reference"], "start")
    (final,) = select(records["reference"], "finished")
    (resumed_final,) = select(records["resume"], "finished")
    require(final == resumed_final and Fraction(*final["loss"]) < Fraction(*initial["loss"]),
            "loss comparison failed")
    fixture_digest = hashlib.sha256(Path(__file__).with_name("train.py").read_bytes()).hexdigest()
    for name in ("reference", "interrupt", "resume"):
        (entry,) = select(records[name], "start")
        require(entry["fixture_digest"] == fixture_digest, "fixture changed")
    return {"outcome": "pass", "fixture_sha256": fixture_digest, "exit_codes": codes,
            "reference_checkpoint_sha256": commits["reference"], "resumed_from_step": loaded["step"],
            "loaded_checkpoint_sha256": loaded["sha256"], "last_update_before_stop": stop["step"],
            "replayed_updates": [r["step"] for r in select(records["resume"], "updated")
                                 if r["step"] <= stop["step"]],
            "replayed_step_count": stop["step"] - loaded["step"],
            "initial_loss_fraction": initial["loss"], "final_loss_fraction": final["loss"],
            "final_loss_decimal": float(Fraction(*final["loss"])), "read_only_verifier": check}
