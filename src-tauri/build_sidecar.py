"""Build the Python sidecar into a single executable via PyInstaller.

Usage:
    python src-tauri/build_sidecar.py

Produces stt-<triple>.exe deployed to the locations Tauri expects.
"""

import os
import shutil
import subprocess
import sys
import glob

SRC_TAURI = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_TAURI)
ENTRY = os.path.join(SRC_TAURI, "sidecar", "main.py")


def get_target_triple():
    try:
        out = subprocess.check_output(["rustc", "-vV"]).decode()
        return out.split("host: ")[1].split("\n")[0].strip()
    except Exception:
        return "x86_64-pc-windows-msvc"


def main():
    os.chdir(SRC_TAURI)
    triple = get_target_triple()
    binary_name = f"stt-{triple}.exe"

    if not os.path.exists(ENTRY):
        print(f"ERROR: entry point not found: {ENTRY}")
        sys.exit(1)

    # Find openwakeword models
    try:
        import openwakeword
        oww_root = os.path.dirname(openwakeword.__file__)
    except ImportError:
        print("ERROR: openwakeword not installed")
        sys.exit(1)

    # Collect openwakeword resources
    temp_models = os.path.join(SRC_TAURI, "temp_models")
    if os.path.exists(temp_models):
        shutil.rmtree(temp_models)
    os.makedirs(temp_models)

    def collect_model(pattern, dest_name):
        for p in glob.glob(os.path.join(oww_root, "resources", "models", pattern)):
            shutil.copy2(p, os.path.join(temp_models, dest_name))
            print(f"Collected {dest_name}")
            return True
        for p in glob.glob(os.path.expanduser(f"~/.openwakeword/{pattern}")):
            shutil.copy2(p, os.path.join(temp_models, dest_name))
            print(f"Collected {dest_name}")
            return True
        return False

    print("Collecting openwakeword models...")
    collect_model("melspectrogram.onnx", "melspectrogram.onnx")
    collect_model("embedding_model.onnx", "embedding_model.onnx")
    collect_model("hey_jarvis*.onnx", "hey_jarvis.onnx")

    cmd = [
        "pyinstaller",
        "--onefile",
        "--noconsole",
        f"--add-data={os.path.join(SRC_TAURI, 'hey_jen.onnx')};.",
        f"--add-data={temp_models};models",
        "--collect-all=openwakeword",
        "--hidden-import=openwakeword",
        "--hidden-import=onnxruntime",
        "--hidden-import=speech_recognition",
        "--hidden-import=pyaudio",
        "--hidden-import=screen_brightness_control",
        "--hidden-import=edge_tts",
        "--hidden-import=httpx",
        "--name=stt",
        ENTRY,
    ]

    print("Compiling sidecar...")
    subprocess.run(cmd, check=True)

    shutil.rmtree(temp_models)

    generated = os.path.join(SRC_TAURI, "dist", "stt.exe")
    if not os.path.exists(generated):
        print("ERROR: PyInstaller failed")
        sys.exit(1)

    # Deploy to all locations Tauri looks for sidecars
    destinations = [
        os.path.join(PROJECT_ROOT, binary_name),          # project root (primary)
        os.path.join(PROJECT_ROOT, "binaries", binary_name),
        os.path.join(SRC_TAURI, binary_name),
        os.path.join(SRC_TAURI, "binaries", binary_name),
    ]
    for dest in destinations:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(generated, dest)
        print(f"Deployed: {dest}")

    shutil.rmtree(os.path.join(SRC_TAURI, "build"), ignore_errors=True)
    shutil.rmtree(os.path.join(SRC_TAURI, "dist"), ignore_errors=True)
    spec = os.path.join(SRC_TAURI, "stt.spec")
    if os.path.exists(spec):
        os.remove(spec)

    print("--- Sidecar build complete ---")


if __name__ == "__main__":
    main()
