import os
import subprocess
import sys
import shutil
import glob

def build():
    # Absolute path to project root and src-tauri
    src_tauri_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(src_tauri_dir)
    os.chdir(src_tauri_dir)
    
    print(f"--- Bulletproof Sidecar Build ---")
    print(f"Project Root: {project_root}")
    print(f"src-tauri: {src_tauri_dir}")

    # Get target triple
    try:
        # Try to get it from rustc for maximum accuracy
        target_triple = subprocess.check_output(["rustc", "-vV"]).decode().split("host: ")[1].split("\n")[0].strip()
        print(f"Detected target triple: {target_triple}")
    except Exception as e:
        print(f"Warning: Could not detect target triple via rustc: {e}")
        target_triple = "x86_64-pc-windows-msvc"
    
    binary_name = f"stt-{target_triple}.exe"
    
    # Run PyInstaller
    script_path = os.path.join(src_tauri_dir, "stt.py")
    hey_jen_model = os.path.join(src_tauri_dir, "hey_jen.onnx")

    # Find openwakeword resources
    try:
        import openwakeword
        oww_root = os.path.dirname(openwakeword.__file__)
    except ImportError:
        print("ERROR: openwakeword not installed")
        sys.exit(1)
    
    # Create a local models directory to collect everything we need
    # This avoids issues with finding them in site-packages during build
    temp_models_dir = os.path.join(src_tauri_dir, "temp_models")
    if os.path.exists(temp_models_dir):
        shutil.rmtree(temp_models_dir)
    os.makedirs(temp_models_dir)

    def collect_model(pattern, dest_name):
        search_patterns = [
            os.path.join(oww_root, "resources", "models", pattern),
            os.path.join(oww_root, "models", pattern),
            os.path.expanduser(f"~/.openwakeword/{pattern}"),
            os.path.expanduser(f"~/.openwakeword/models/{pattern}"),
        ]
        
        for p in search_patterns:
            matches = glob.glob(p)
            if matches:
                # Filter for .onnx if pattern doesn't specify
                onnx_matches = [m for m in matches if m.endswith(".onnx")]
                if onnx_matches:
                    target = os.path.join(temp_models_dir, dest_name)
                    shutil.copy2(onnx_matches[0], target)
                    print(f"Collected {dest_name} from {onnx_matches[0]}")
                    return True
        return False

    print("Collecting required openwakeword models...")
    melspec = collect_model("melspectrogram.onnx", "melspectrogram.onnx")
    embed = collect_model("embedding_model.onnx", "embedding_model.onnx")
    jarvis = collect_model("hey_jarvis*.onnx", "hey_jarvis.onnx")
    
    if not (melspec and embed):
        print("WARNING: Could not find base models. Attempting to download...")
        try:
            from openwakeword.utils import download_models
            download_models()
            # Try again
            collect_model("melspectrogram.onnx", "melspectrogram.onnx")
            collect_model("embedding_model.onnx", "embedding_model.onnx")
            collect_model("hey_jarvis*.onnx", "hey_jarvis.onnx")
        except Exception as e:
            print(f"Failed to download models: {e}")

    cmd = [
        "pyinstaller",
        "--onefile",
        "--noconsole",
        f"--add-data={hey_jen_model};.",
        f"--add-data={temp_models_dir};models",
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

    # Cleanup temp models
    shutil.rmtree(temp_models_dir)

    generated_exe = os.path.join(src_tauri_dir, "dist", "stt.exe")

    if not os.path.exists(generated_exe):
        print("ERROR: PyInstaller failed to create stt.exe")
        sys.exit(1)

    # List of destinations to ensure Tauri finds it
    destinations = [
        os.path.join(src_tauri_dir, "binaries", binary_name), # Standard v2 location
        os.path.join(src_tauri_dir, binary_name),            # Root of src-tauri (fallback)
        os.path.join(project_root, "binaries", binary_name), # Root of project (fallback)
        os.path.join(project_root, binary_name)              # Root of project (fallback)
    ]

    for dest in destinations:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(generated_exe, dest)
        print(f"Deployed to: {dest}")

    # Cleanup
    shutil.rmtree(os.path.join(src_tauri_dir, "build"), ignore_errors=True)
    shutil.rmtree(os.path.join(src_tauri_dir, "dist"), ignore_errors=True)
    spec_file = os.path.join(src_tauri_dir, "stt.spec")
    if os.path.exists(spec_file):
        os.remove(spec_file)

    print(f"--- Sidecar Deployed Successfully ---")

if __name__ == "__main__":
    build()
