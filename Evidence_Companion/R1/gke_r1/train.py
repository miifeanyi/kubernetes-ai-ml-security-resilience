"""Fixed full-batch linear regression using exact rational arithmetic."""
import argparse
import hashlib
import json
import math
import os
import tempfile
from fractions import Fraction
from pathlib import Path

DATA = [(x, 2 * x + 1) for x in range(4)]
RATE = Fraction(1, 32)
# The dataset and update code both live in this file.
FIXTURE_DIGEST = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def emit(event, **fields):
    print(json.dumps({"event": event, **fields}, sort_keys=True), flush=True)


def encode(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")


def pair(value):
    return [value.numerator, value.denominator]


def loss(slope, intercept):
    return sum((slope * x + intercept - y) ** 2 for x, y in DATA) / len(DATA)


def update(slope, intercept):
    errors = [(x, slope * x + intercept - y) for x, y in DATA]
    scale = RATE * 2 / len(DATA)
    return (slope - scale * sum(x * err for x, err in errors),
            intercept - scale * sum(err for _, err in errors))


def commit(directory, step, slope, intercept):
    payload = encode({"schema_version": 1, "fixture_digest": FIXTURE_DIGEST,
                      "step": step, "slope": pair(slope), "intercept": pair(intercept)})
    final_path = directory / f"step-{step:04d}.json"
    with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
        temp_path = Path(stream.name)
        try:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp_path, final_path)
        directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temp_path.unlink(missing_ok=True)
    emit("committed", step=step, sha256=hashlib.sha256(payload).hexdigest())


def valid_fraction(parts):
    return (isinstance(parts, list) and len(parts) == 2 and
            all(type(value) is int for value in parts) and
            parts[1] > 0 and math.gcd(*parts) == 1)


def load_step_four(directory):
    path = directory / "step-0004.json"
    if not path.is_file():
        emit("missing_checkpoint", step=4)
        raise SystemExit(41)
    if set(directory.glob("step-*.json")) != {path}:
        emit("unexpected_checkpoint_set")
        raise SystemExit(43)
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != os.environ.get("EXPECTED_H4"):
        emit("checkpoint_digest_mismatch", step=4, observed=digest)
        raise SystemExit(43)
    record = json.loads(payload)
    if not (type(record) is dict and set(record) == {
            "schema_version", "fixture_digest", "step", "slope", "intercept"}
            and type(record["schema_version"]) is int and record["schema_version"] == 1
            and type(record["step"]) is int and record["step"] == 4
            and record["fixture_digest"] == FIXTURE_DIGEST
            and valid_fraction(record["slope"]) and valid_fraction(record["intercept"])
            and encode(record) == payload):
        emit("invalid_checkpoint", step=4)
        raise SystemExit(43)
    emit("loaded", step=4, sha256=digest)
    return record["step"], Fraction(*record["slope"]), Fraction(*record["intercept"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["fresh", "resume"])
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--save-every", type=int, default=4)
    parser.add_argument("--exit-after-update", type=int)
    args = parser.parse_args()
    if args.steps < 1 or args.save_every < 1:
        parser.error("steps and save-every must be positive")
    if args.mode == "resume":
        start, slope, intercept = load_step_four(args.dir)
    else:
        args.dir.mkdir(parents=True, exist_ok=True)
        if any(args.dir.iterdir()):
            parser.error("fresh mode requires an empty directory")
        start, slope, intercept = 0, Fraction(0), Fraction(0)
    emit("start", step=start, loss=pair(loss(slope, intercept)), fixture_digest=FIXTURE_DIGEST)
    for step in range(start + 1, args.steps + 1):
        slope, intercept = update(slope, intercept)
        emit("updated", step=step)
        if step % args.save_every == 0:
            commit(args.dir, step, slope, intercept)
        if step == args.exit_after_update:
            emit("deliberate_exit", step=step, code=42)
            return 42
    emit("finished", step=args.steps, loss=pair(loss(slope, intercept)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
