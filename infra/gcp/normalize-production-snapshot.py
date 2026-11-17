"""Canonicalize metadata snapshots; ignore mount order, preserve every mount field.

Accepts structured JSON lines and the earlier space-separated Docker format.
Never queries Docker, reads secrets or changes host state.
"""

import json
import re
import sys
from pathlib import Path


def normalize(lines):
    output, containers = [], 0
    for raw in lines:
        line = raw.rstrip("\r\n")
        if not line.strip():
            continue
        if re.fullmatch(r"[a-f0-9]{64} [ *].+", line):
            output.append(line)
            continue
        if line.lstrip().startswith("{"):
            record = json.loads(line)
        else:
            # Legacy: name id image started_at restart_count PORTS_JSON MOUNTS_JSON.
            name, identity, image, started, restarts, rest = line.split(maxsplit=5)
            decoder = json.JSONDecoder()
            ports, end = decoder.raw_decode(rest)
            mounts, end2 = decoder.raw_decode(rest[end:].lstrip())
            if rest[end:].lstrip()[end2:].strip():
                raise ValueError("Unexpected legacy snapshot data")
            record = {
                "name": name,
                "id": identity,
                "image": image,
                "started_at": started,
                "restart_count": int(restarts),
                "ports": ports,
                "mounts": mounts,
            }
        if (
            not {
                "name",
                "id",
                "image",
                "started_at",
                "restart_count",
                "ports",
                "mounts",
            }
            <= record.keys()
        ):
            raise ValueError("Incomplete container metadata")
        mounts = record["mounts"]
        if not isinstance(mounts, list) or not all(isinstance(m, dict) for m in mounts):
            raise ValueError("Invalid mount metadata")
        record["mounts"] = sorted(mounts, key=lambda m: json.dumps(m, sort_keys=True))
        output.append(json.dumps(record, sort_keys=True, separators=(",", ":")))
        containers += 1
    if not containers:
        raise ValueError("Snapshot contains no container metadata")
    return "\n".join(sorted(output)) + "\n"


if __name__ == "__main__":
    try:
        if len(sys.argv) == 2:
            result = normalize(
                Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
            )
        else:
            result = normalize(sys.stdin)
        sys.stdout.write(result)
    except (ValueError, KeyError, TypeError, OSError):
        sys.exit("Invalid production snapshot; comparison rejected")
