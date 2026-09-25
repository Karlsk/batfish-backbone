"""Runs in a networkless one-shot container, with only the two owned volumes mounted."""

import os
import sys
import tarfile
from pathlib import Path


def regular(member):
    if not (member.isdir() or member.isfile()):
        raise ValueError("Only regular files and directories may be backed up")
    return member


def extract_member(member, destination):
    return tarfile.data_filter(regular(member), destination)


for name in ["appdata", "enginedata"]:
    root = Path("/") / name
    archive = Path("/backup") / (name + ".tar")
    if sys.argv[1] == "backup":
        with tarfile.open(archive, "w") as bundle:
            bundle.add(root, arcname=".", filter=regular)
        archive.chmod(0o600)
    elif sys.argv[1] == "restore":
        with tarfile.open(archive, "r") as bundle:
            bundle.extractall(root, filter=extract_member)
        # data_filter drops archived directory modes and ownership. Re-establish the
        # private storage contract before any application or engine process starts.
        for path in [root, *root.rglob("*")]:
            os.chown(path, 10001, 10001, follow_symlinks=False)
            path.chmod(0o700 if path.is_dir() else 0o600)
    else:
        raise ValueError("Expected backup or restore")
