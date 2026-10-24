"""aiMontage evidence-first video analysis workflow."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

TOOL_MODULES = {
    "audio_probe": "tools.analysis.audio_probe:AudioProbe",
    "scene_detect": "tools.analysis.scene_detect:SceneDetect",
    "frame_sampler": "tools.analysis.frame_sampler:FrameSampler",
    "transcript_fetcher": "tools.analysis.transcript_fetcher:TranscriptFetcher",
    "transcriber": "tools.analysis.transcriber:Transcriber",
    "video_analyzer": "tools.analysis.video_analyzer:VideoAnalyzer",
}


class UpstreamToolError(RuntimeError):
    pass


def run_upstream_tool(
    tool_name: str,
    inputs: dict[str, Any],
    *,
    repo_root: str | Path = "vendor/OpenMontage",
    timeout_seconds: int = 900,
) -> dict[str, Any]:
    """Run a pinned upstream BaseTool in its own checkout, without copying code."""
    if tool_name not in TOOL_MODULES:
        raise ValueError(f"Unsupported upstream tool: {tool_name}")
    root = Path(repo_root).resolve()
    if not (root / "tools" / "base_tool.py").is_file():
        raise UpstreamToolError(
            f"OpenMontage submodule is not initialized at {root}. "
            "Run: git submodule update --init --recursive"
        )
    runner = r'''
import dataclasses, importlib, json, sys
spec, class_name = sys.argv[1].split(":", 1)
inputs = json.loads(sys.stdin.read())
module = importlib.import_module(spec)
tool = getattr(module, class_name)()
result = tool.execute(inputs)
if dataclasses.is_dataclass(result):
    payload = dataclasses.asdict(result)
elif hasattr(result, "model_dump"):
    payload = result.model_dump()
elif hasattr(result, "__dict__"):
    payload = vars(result)
else:
    payload = result
print(json.dumps(payload, ensure_ascii=False, default=str))
'''
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-c", runner, TOOL_MODULES[tool_name]],
        input=json.dumps(inputs, ensure_ascii=False),
        text=True,
        capture_output=True,
        cwd=root,
        env=env,
        timeout=timeout_seconds,
        check=False,
    )
    if proc.returncode:
        raise UpstreamToolError(
            f"{tool_name} failed (exit {proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise UpstreamToolError(f"{tool_name} returned non-JSON output") from exc
    if not isinstance(payload, dict):
        raise UpstreamToolError(f"{tool_name} returned an unexpected result type")
    return payload
