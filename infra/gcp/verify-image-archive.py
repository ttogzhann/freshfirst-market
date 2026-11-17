"""Validate a Docker-save archive, then stream only verified untagged image content.

No extraction, registry access, credentials, third-party packages or Docker calls.
"""

import gzip
import hashlib
import io
import json
import re
import shutil
import sys
import tarfile
from contextlib import contextmanager
from pathlib import PurePosixPath

MAX_EXPANDED_BYTES = 1024 * 1024 * 1024


@contextmanager
def layer_stream(archive, member):
    with archive.extractfile(member) as raw:
        magic = raw.read(4)
        raw.seek(0)
        if magic.startswith(b"\x1f\x8b"):
            with gzip.GzipFile(fileobj=raw) as decoded:
                yield decoded
        else:
            yield raw


def safe_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or str(path) in {"", "."}:
        raise ValueError("Unsafe archive path")
    return str(path)


def normalize(
    archive_path, image_id, output, docker_root=None, max_expanded_bytes=None
):
    limit = MAX_EXPANDED_BYTES if max_expanded_bytes is None else max_expanded_bytes
    if not 0 < limit <= MAX_EXPANDED_BYTES:
        raise ValueError("Invalid expanded layer limit")
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image_id):
        raise ValueError("Invalid image ID")
    with tarfile.open(archive_path, "r:") as archive:
        members = {}
        for n, member in enumerate(archive):
            if n >= 4096 or not (member.isfile() or member.isdir()):
                raise ValueError("Unsupported archive member")
            name = safe_name(member.name)
            if name in members:
                raise ValueError("Duplicate archive member")
            members[name] = member

        def metadata(name, limit):
            member = members[safe_name(name)]
            if not member.isfile() or member.size > limit:
                raise ValueError("Invalid archive metadata size/type")
            return archive.extractfile(member).read()

        manifest = json.loads(metadata("manifest.json", 65536))
        if not isinstance(manifest, list) or len(manifest) != 1:
            raise ValueError("Exactly one image required")
        image = manifest[0]
        if image.get("RepoTags") not in (None, []):
            raise ValueError("Archive must be untagged")
        config = metadata(image["Config"], 8 * 1024 * 1024)
        if "sha256:" + hashlib.sha256(config).hexdigest() != image_id:
            raise ValueError("Image config digest mismatch")
        settings = json.loads(config)
        if settings.get("os") != "linux" or settings.get("architecture") != "amd64":
            raise ValueError("Expected linux/amd64 image")
        if settings["rootfs"]["type"] != "layers":
            raise ValueError("Unsupported rootfs")
        layers = [members[safe_name(name)] for name in image["Layers"]]
        digests = settings["rootfs"]["diff_ids"]
        if len(layers) != len(digests):
            raise ValueError("Layer count mismatch")
        sizes, expanded = [], 0
        for layer, expected in zip(layers, digests, strict=True):
            if not layer.isfile():
                raise ValueError("Invalid layer type")
            digest = hashlib.sha256()
            size = 0
            with layer_stream(archive, layer) as stream:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    expanded += len(chunk)
                    if expanded > limit:
                        raise ValueError("Expanded layer size limit exceeded")
                    digest.update(chunk)
            sizes.append(size)
            if "sha256:" + digest.hexdigest() != expected:
                raise ValueError("Layer digest mismatch")
        if (
            shutil.disk_usage(docker_root or archive_path).free
            < 2 * expanded + 536870912
        ):
            raise ValueError("Insufficient expanded image disk headroom")

        # Do not forward OCI index annotations, tags, extra files or archive paths.
        # This keeps Docker load from changing any existing production image tag.
        config_name = image_id.removeprefix("sha256:") + ".json"
        layer_names = [f"layers/{n}/layer.tar" for n in range(len(layers))]
        clean_manifest = json.dumps(
            [{"Config": config_name, "RepoTags": None, "Layers": layer_names}]
        ).encode()
        with tarfile.open(fileobj=output, mode="w|") as clean:
            for name, contents in (
                ("manifest.json", clean_manifest),
                (config_name, config),
            ):
                member = tarfile.TarInfo(name)
                member.size = len(contents)
                clean.addfile(member, io.BytesIO(contents))
            for name, layer, size in zip(layer_names, layers, sizes, strict=True):
                member = tarfile.TarInfo(name)
                member.size = size
                with layer_stream(archive, layer) as stream:
                    clean.addfile(member, stream)


if __name__ == "__main__":
    try:
        normalize(
            sys.argv[1],
            sys.argv[2],
            sys.stdout.buffer,
            sys.argv[3] if len(sys.argv) > 3 else None,
            int(sys.argv[4]) if len(sys.argv) > 4 else None,
        )
    except (
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        OSError,
        EOFError,
        tarfile.TarError,
    ):
        sys.exit("Invalid image archive; import rejected")
