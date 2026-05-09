import os
import subprocess
import sys
import shutil

def build():
    # Absolute path to project root and src-tauri
    src_tauri_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(src_tauri_dir)
    os.chdir(src_tauri_dir)
    
    print(f"--- Bulletproof Sidecar Build ---")
    print(f"Project Root: {project_root}")
    print(f"src-tauri: {src_tauri_dir}")

    target_triple = "x86_64-pc-windows-msvc"
    binary_name = f"stt-{target_triple}.exe"
    
    # Run PyInstaller
    script_path = os.path.join(src_tauri_dir, "stt.py")
    model_path = os.path.join(src_tauri_dir, "hey_jen.onnx")
    
    cmd = [
        "pyinstaller",
        "--onefile",
        "--noconsole",
        f"--add-data={model_path};.",
        "--collect-all=openwakeword",
        "--hidden-import=openwakeword",
        "--hidden-import=onnxruntime",
        "--hidden-import=speech_recognition",
        "--hidden-import=pyaudio",
        "--name=stt",
        script_path
    ]

    print(f"Compiling sidecar...")
    subprocess.run(cmd, check=True)

    generated_exe = os.path.join(src_tauri_dir, "dist", "stt.exe")

    if not os.path.exists(generated_exe):
        print("ERROR: PyInstaller failed to create stt.exe")
        sys.exit(1)

    # List of all possible locations Tauri v2 might look
    destinations = [
        os.path.join(src_tauri_dir, "binaries", binary_name),
        os.path.join(src_tauri_dir, binary_name),
        os.path.join(project_root, "binaries", binary_name),
        os.path.join(project_root, binary_name)
    ]

    for dest in destinations:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(generated_exe, dest)
        print(f"Deployed to: {dest}")

    print(f"--- Sidecar Deployed Successfully ---")

if __name__ == "__main__":
    build()
