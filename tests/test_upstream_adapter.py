import pytest
from aimontage.upstream import UpstreamToolError, run_upstream_tool

def test_unknown_tool_rejected():
    with pytest.raises(ValueError):
        run_upstream_tool("not-a-tool", {})

def test_missing_submodule_has_actionable_error(tmp_path):
    with pytest.raises(UpstreamToolError, match="submodule is not initialized"):
        run_upstream_tool("audio_probe", {}, repo_root=tmp_path)
