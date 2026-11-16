"""Validate successful dev metadata before production OIDC authentication."""

import json
import re
import sys
from pathlib import Path


def verify(release, run, ci, repository, digest, source_sha, run_id):
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
        raise ValueError("Invalid digest")
    if not re.fullmatch(r"[a-f0-9]{40}", source_sha):
        raise ValueError("Invalid source SHA")
    if not str(run_id).isdigit():
        raise ValueError("Invalid dev workflow run ID")
    if not (
        run["id"] == int(run_id)
        and run["repository"]["full_name"] == repository
        and run["event"] == "workflow_run"
        and run["conclusion"] == "success"
        and run["path"] == ".github/workflows/gcp.yml"
        and ci["id"] == release["ci_run_id"]
        and ci["repository"]["full_name"] == repository
        and ci["head_repository"]["full_name"] == repository
        and ci["event"] == "push"
        and ci["head_branch"] == "feature/render-deployment"
        and ci["head_sha"] == source_sha
        and ci["path"] == ".github/workflows/render.yml"
        and ci["conclusion"] == "success"
        and release["repository"] == repository
        and release["source_sha"] == source_sha
        and release["digest"] == digest
        and release["dev_run_id"] == int(run_id)
        and release["dev_healthy"] is True
    ):
        raise ValueError("Release does not match a successful dev deployment")
    image = release["image"]
    if not re.fullmatch(
        r"[a-z0-9-]+-docker\.pkg\.dev/[a-z0-9-]+/[a-z0-9_-]+/[a-z0-9/_-]+@" + digest,
        image,
    ):
        raise ValueError("Invalid release image")
    return image


if __name__ == "__main__":
    print(
        verify(
            *(json.loads(Path(path).read_text()) for path in sys.argv[1:4]),
            *sys.argv[4:],
        )
    )
