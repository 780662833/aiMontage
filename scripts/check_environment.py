from __future__ import annotations
import importlib.util, shutil, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBMODULE = ROOT / "vendor" / "OpenMontage"

def binary_version(name: str) -> str:
    path = shutil.which(name)
    if not path:
        return "MISSING"
    proc = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=10)
    lines = (proc.stdout or proc.stderr).splitlines()
    return lines[0] if lines else f"FOUND: {path}"

def main() -> int:
    print(f"Python: {binary_version('python')}")
    print(f"ffmpeg: {binary_version('ffmpeg')}")
    print(f"ffprobe: {binary_version('ffprobe')}")
    print(f"OpenMontage submodule: {'initialized' if (SUBMODULE / 'tools' / 'base_tool.py').is_file() else 'NOT INITIALIZED'}")
    for module in ("yaml", "pydantic", "jsonschema", "PIL", "numpy", "scenedetect", "youtube_transcript_api", "faster_whisper"):
        print(f"Python module {module}: {'installed' if importlib.util.find_spec(module) else 'MISSING'}")
    return 0 if shutil.which("ffmpeg") and shutil.which("ffprobe") and (SUBMODULE / "tools" / "base_tool.py").is_file() else 1

if __name__ == "__main__":
    raise SystemExit(main())
