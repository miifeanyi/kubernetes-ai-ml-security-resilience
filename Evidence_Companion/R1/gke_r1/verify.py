"""Independent, read-only comparison of final checkpoint files."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("resumed", type=Path)
    args = parser.parse_args()
    results = []
    for path in (args.reference, args.resumed):
        raw = path.read_bytes()
        checkpoint = json.loads(raw)
        results.append({"step": checkpoint["step"], "sha256": hashlib.sha256(raw).hexdigest()})
    equal = (all(type(item["step"]) is int and item["step"] == 12 for item in results)
             and results[0]["sha256"] == results[1]["sha256"])
    print(json.dumps({"event": "compared", "reference": results[0], "resumed": results[1],
                      "matches": equal}, sort_keys=True))
    return 0 if equal else 1


if __name__ == "__main__":
    raise SystemExit(main())
