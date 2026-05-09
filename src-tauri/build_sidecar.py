import os
import subprocess
import sys
import shutil

def build():
    # Get current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_dir)

    # Define paths
    script_path = "stt.py"
    model_path = "hey_jen.onnx"
    output_dir = "binaries"
    
    # Get target triple from rustc
    try:
        target_triple = subprocess.check_output(["rustc", "-vV"]).decode().split("host: ")[1].split("\n")[0].strip()
    except:
        target_triple = "x86_64-pc-windows-msvc" # Fallback

    binary_name = f"stt-{target_triple}.exe"

    print(f"Building sidecar for {target_triple}...")

    # Ensure output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # PyInstaller command
    cmd = [
        "pyinstaller",
        "--onefile",
        "--noconsole",
        f"--add-data={model_path};.",
        "--hidden-import=openwakeword",
        "--hidden-import=onnxruntime",
        "--hidden-import=speech_recognition",
        "--hidden-import=pyaudio",
        "--name=stt",
        script_path
    ]

    # Run PyInstaller
    subprocess.run(cmd, check=True)

    # Move and rename the binary
    dist_path = os.path.join("dist", "stt.exe")
    final_path = os.path.join(output_dir, binary_name)

    if os.path.exists(final_path):
        os.remove(final_path)
    
    shutil.move(dist_path, final_path)

    print(f"Success! Sidecar built at: {final_path}")

    # Cleanup build artifacts
    shutil.rmtree("build", ignore_errors=True)
    shutil.rmtree("dist", ignore_errors=True)
    if os.path.exists("stt.spec"):
        os.remove("stt.spec")

if __name__ == "__main__":
    build()
