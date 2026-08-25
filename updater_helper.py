"""Replace a portable onedir build after the main app has exited."""
import argparse
import ctypes
import os
import shutil
import subprocess
import tempfile
import zipfile


def wait_for_process(pid):
    handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)
    if not handle:
        return
    ctypes.windll.kernel32.WaitForSingleObject(handle, 30 * 1000)
    ctypes.windll.kernel32.CloseHandle(handle)


def safe_extract(archive, destination):
    root = os.path.abspath(destination)
    with zipfile.ZipFile(archive) as package:
        for item in package.infolist():
            path = os.path.abspath(os.path.join(destination, item.filename))
            if os.path.commonpath((root, path)) != root:
                raise ValueError("Update archive contains an unsafe path.")
        package.extractall(destination)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--executable", required=True)
    args = parser.parse_args()
    wait_for_process(args.pid)
    staging = tempfile.mkdtemp(prefix="scpsl-autojoin-")
    try:
        safe_extract(args.archive, staging)
        shutil.copytree(staging, args.target, dirs_exist_ok=True)
        subprocess.Popen([args.executable])
    finally:
        try:
            os.remove(args.archive)
        except OSError:
            pass
        shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    main()
