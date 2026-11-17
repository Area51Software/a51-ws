import pytest


@pytest.fixture
def isolated_workspaces_folder(tmp_path, monkeypatch):
    """Every test saves into its own empty folder; the real ~/.config/a51-ws is never touched."""
    monkeypatch.setenv("A51_WS_FOLDER", str(tmp_path))
    return tmp_path


def pane(folder, runs_claude=False):
    return {"type": "pane", "folder": folder, "profile": "Default",
            "runs_claude": runs_claude, "appearance": {}}


@pytest.fixture
def sample_windows():
    return [{"frame": [0, 0, 800, 600], "tabs": [
        pane("/work/a", runs_claude=True),
        {"type": "split", "side_by_side": True, "children": [pane("/work/b"), pane("/work/c")]},
    ]}]
