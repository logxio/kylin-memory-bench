#!/usr/bin/env python3
"""Build an architecture-independent Debian package with Python's standard library."""

import gzip
import hashlib
import io
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"
NAME = f"kylin-memory-bench_{VERSION}_all.deb"
CONTROL = f"""Package: kylin-memory-bench
Version: {VERSION}
Section: science
Priority: optional
Architecture: all
Maintainer: Yan Su <hi@yansu.me>
Depends: python3 (>= 3.10), python3-websocket
Description: Evidence-based six-ability long-term memory benchmark for agents
""".encode()
LAUNCHER = b"""#!/bin/sh
cd /usr/share/kylin-memory-bench || exit 1
exec python3 -m kylin_memory_bench "$@"
"""


def archive(files):
    directories = set()
    for name, _, _ in files:
        parts = name.split("/")
        for length in range(1, len(parts)):
            directories.add("/".join(parts[:length]))

    raw = io.BytesIO()
    with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.GNU_FORMAT) as tar:
            entries = [(name, None, 0o755) for name in directories] + files
            for name, data, mode in sorted(entries, key=lambda entry: entry[0]):
                info = tarfile.TarInfo("./" + name + ("/" if data is None else ""))
                info.mode = mode
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ""
                if data is None:
                    info.type = tarfile.DIRTYPE
                    tar.addfile(info)
                else:
                    info.size = len(data)
                    tar.addfile(info, io.BytesIO(data))
    return raw.getvalue()


def ar_member(name, data):
    identifier = name.ljust(16)
    header = (f"{identifier}{0:<12}{0:<6}{0:<6}{'100644':<8}{len(data):<10}`\n").encode("ascii")
    if len(header) != 60:
        raise ValueError("invalid ar header")
    return header + data + (b"\n" if len(data) % 2 else b"")


def main():
    selections = ["kylin_memory_bench", "data", "configs", "docs", "examples",
                  "run-fixture.sh", "run-live.sh", "requirements.txt", "README.md",
                  "CONTRIBUTING.md", "LICENSE"]
    files = [("usr/bin/kylin-memory-bench", LAUNCHER, 0o755)]
    for name in selections:
        source = ROOT / name
        paths = sorted(source.rglob("*")) if source.is_dir() else [source]
        for path in paths:
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            relative = path.relative_to(ROOT)
            mode = 0o755 if relative.name.endswith(".sh") else 0o644
            files.append(("usr/share/kylin-memory-bench/" + relative.as_posix(), path.read_bytes(), mode))
    output = ROOT / "dist" / NAME
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = (b"!<arch>\n" + ar_member("debian-binary", b"2.0\n") +
               ar_member("control.tar.gz", archive([("control", CONTROL, 0o644)])) +
               ar_member("data.tar.gz", archive(files)))
    output.write_bytes(payload)
    print(output)
    print("SHA-256", hashlib.sha256(payload).hexdigest())
    print("files", len(files))


if __name__ == "__main__":
    main()
