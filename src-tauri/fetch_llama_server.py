"""Fetch llama.cpp release binaries (llama-server + DLLs) for Tauri sidecar.

Usage:
    python src-tauri/fetch_llama_server.py                 # CPU build (bundled)
    python src-tauri/fetch_llama_server.py --variant vulkan  # GPU runtime (app data)
    python src-tauri/fetch_llama_server.py --tag b11060

The CPU build is bundled into the installer. The Vulkan build is an optional
GPU runtime installed to the app data dir (same place Settings downloads it
to), so it can be enabled with the GPU Acceleration toggle.
"""

import argparse
import glob
import io
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

REPO = "https://github.com/ggml-org/llama.cpp/releases/download"
DEFAULT_TAG = "b11060"
VARIANTS = {
    "cpu": "llama-{tag}-bin-win-cpu-x64.zip",
    "vulkan": "llama-{tag}-bin-win-vulkan-x64.zip",
}


def get_target_triple():
    try:
        out = __import__("subprocess").check_output(["rustc", "-vV"]).decode()
        return out.split("host: ")[1].split("\n")[0].strip()
    except Exception:
        return "x86_64-pc-windows-msvc"


def main():
    parser = argparse.ArgumentParser(description="Fetch llama-server sidecar binaries")
    parser.add_argument("--tag", default=DEFAULT_TAG, help="llama.cpp release tag (default: %(default)s)")
    parser.add_argument("--variant", default="cpu", choices=sorted(VARIANTS),
                        help="cpu = bundled sidecar; vulkan = GPU runtime in app data")
    parser.add_argument("--dest", default=None, help="override install directory")
    args = parser.parse_args()

    src_tauri_dir = os.path.dirname(os.path.abspath(__file__))

    # All sidecar files go in src-tauri/binaries/ (DLLs) and src-tauri/ (exe)
    # so the Tauri build script can find them and resources can be bundled.
    binaries_dir = os.path.join(src_tauri_dir, "binaries")
    os.makedirs(binaries_dir, exist_ok=True)

    triple = get_target_triple()
    if "windows" not in triple:
        print(f"ERROR: This script fetches Windows binaries, but target is {triple}")
        sys.exit(1)

    asset = VARIANTS[args.variant].format(tag=args.tag)
    url = f"{REPO}/{args.tag}/{asset}"
    print(f"Downloading {url} ...")

    try:
        with urllib.request.urlopen(url, timeout=120) as resp:
            data = resp.read()
    except Exception as e:
        print(f"ERROR: download failed: {e}")
        sys.exit(1)

    print(f"Downloaded {len(data) / 1024 / 1024:.1f} MB")

    if args.variant == "vulkan":
        dest_dir = args.dest or os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            "com.sehaj.jen",
            "llama-vulkan",
        )
        os.makedirs(dest_dir, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(dest_dir)
        dest_exe = os.path.join(dest_dir, "llama-server.exe")
        if not os.path.exists(dest_exe):
            print(f"ERROR: llama-server.exe not found in {asset}")
            sys.exit(1)
        print(f"GPU runtime installed to {dest_dir}")
        print("Enable it in Jen Settings > AI > GPU Acceleration.")
        return

    exe_name = f"llama-server-{triple}.exe"
    dest_exe = os.path.join(src_tauri_dir, exe_name)
    placed = []

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        with tempfile.TemporaryDirectory() as tmp:
            zf.extractall(tmp)
            for root, _dirs, files in os.walk(tmp):
                for f in files:
                    src = os.path.join(root, f)
                    if f == "llama-server.exe":
                        shutil.copy2(src, dest_exe)
                        placed.append(dest_exe)
                    elif f.lower().endswith(".dll"):
                        dest = os.path.join(binaries_dir, f)
                        shutil.copy2(src, dest)
                        placed.append(dest)

    if not os.path.exists(dest_exe):
        print(f"ERROR: llama-server.exe not found in {asset}. Archive contents: {names}")
        sys.exit(1)

    # Also copy the exe to the project root for the Tauri build script
    project_root = os.path.dirname(src_tauri_dir)
    root_exe = os.path.join(project_root, exe_name)
    shutil.copy2(dest_exe, root_exe)

    print(f"Placed sidecar: {dest_exe}")
    print(f"Placed {root_exe}")
    print(f"Placed {len(placed) - 1} DLLs in {binaries_dir}")
    print("Done. llama-server is ready as a Tauri sidecar.")


if __name__ == "__main__":
    main()
