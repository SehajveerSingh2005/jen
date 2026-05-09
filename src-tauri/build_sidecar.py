import os
import subprocess
import sys
import shutil

def build():
    # Get the absolute path to the src-tauri directory
    src_tauri_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(src_tauri_dir)

    # Define paths
    script_path = os.path.join(src_tauri_dir, "stt.py")
    model_path = os.path.join(src_tauri_dir, "hey_jen.onnx")
    output_dir = os.path.join(src_tauri_dir, "binaries")
    
    # Get target triple
    try:
        target_triple = subprocess.check_output(["rustc", "-vV"]).decode().split("host: ")[1].split("\n")[0].strip()
    except:
        target_triple = "x86_64-pc-windows-msvc"

    binary_name = f"stt-{target_triple}.exe"

    print(f"Target Triple: {target_triple}")
    print(f"Output Directory: {output_dir}")
    print(f"Final Binary Name: {binary_name}")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # PyInstaller command
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

    print(f"Executing: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    # Move and rename the binary
    dist_exe = os.path.join(src_tauri_dir, "dist", "stt.exe")
    final_path = os.path.join(output_dir, binary_name)

    if not os.path.exists(dist_exe):
        print(f"ERROR: PyInstaller failed. {dist_exe} not found.")
        sys.exit(1)

    if os.path.exists(final_path):
        os.remove(final_path)
    
    shutil.move(dist_exe, final_path)
    print(f"SUCCESS: Moved {dist_exe} to {final_path}")

    # Cleanup
    shutil.rmtree(os.path.join(src_tauri_dir, "build"), ignore_errors=True)
    shutil.rmtree(os.path.join(src_tauri_dir, "dist"), ignore_errors=True)
    spec_file = os.path.join(src_tauri_dir, "stt.spec")
    if os.path.exists(spec_file):
        os.remove(spec_file)

if __name__ == "__main__":
    build()
