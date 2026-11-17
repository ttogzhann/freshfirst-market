"""Focused normalization checks; no Docker, GCP or production data access."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "snapshot", ROOT / "infra/gcp/normalize-production-snapshot.py"
)
SNAPSHOT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SNAPSHOT)


def record():
    return {
        "name": "/caddy",
        "id": "container-id",
        "image": "sha256:image",
        "started_at": "2026-11-17T00:00:00Z",
        "restart_count": 0,
        "ports": {"443/tcp": [{"HostIp": "0.0.0.0", "HostPort": "443"}]},
        "mounts": [
            {
                "Type": "volume",
                "Name": "data",
                "Source": "/vol/data",
                "Destination": "/data",
                "RW": True,
            },
            {
                "Type": "volume",
                "Name": "config",
                "Source": "/vol/config",
                "Destination": "/config",
                "RW": True,
            },
        ],
    }


def test_only_mount_and_record_order_are_ignored_for_old_and_new_snapshots():
    a = record()
    b = copy.deepcopy(a)
    b["mounts"].reverse()
    digest = "a" * 64 + "  /opt/freshfirst/compose.yaml"
    old = " ".join(
        [
            a["name"],
            a["id"],
            a["image"],
            a["started_at"],
            str(a["restart_count"]),
            json.dumps(a["ports"]),
            json.dumps(a["mounts"]),
        ]
    )
    assert SNAPSHOT.normalize([digest, old]) == SNAPSHOT.normalize(
        [json.dumps(b), digest]
    )


@pytest.mark.parametrize(
    "change",
    [
        "container",
        "image",
        "started",
        "restart",
        "mount-source",
        "mount-name",
        "mount-rw",
        "ports",
        "compose-hash",
    ],
)
def test_real_metadata_changes_still_fail_comparison(change):
    a = record()
    b = copy.deepcopy(a)
    if change == "container":
        b["id"] = "replacement-container"
    elif change in {"image", "started", "restart"}:
        b[
            {"image": "image", "started": "started_at", "restart": "restart_count"}[
                change
            ]
        ] = "changed"
    elif change == "compose-hash":
        assert SNAPSHOT.normalize(
            [json.dumps(a), "a" * 64 + "  /compose.yaml"]
        ) != SNAPSHOT.normalize([json.dumps(a), "b" * 64 + "  /compose.yaml"])
        return
    elif change == "ports":
        b["ports"]["443/tcp"][0]["HostPort"] = "8443"
    else:
        b["mounts"][0][
            {"mount-source": "Source", "mount-name": "Name", "mount-rw": "RW"}[change]
        ] = "changed"
    assert SNAPSHOT.normalize([json.dumps(a)]) != SNAPSHOT.normalize([json.dumps(b)])


def test_empty_or_incomplete_snapshot_is_not_a_pass():
    for lines in [[], ["a" * 64 + "  /file"], ['{"mounts": []}']]:
        with pytest.raises(ValueError):
            SNAPSHOT.normalize(lines)
