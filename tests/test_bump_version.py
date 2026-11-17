"""The stamp step must never let a version go backwards (tuple order, left to right)."""
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUMP_SCRIPT = PROJECT_ROOT / "scripts" / "bump-version.sh"


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   check=True, capture_output=True)


def run_bump(repo):
    return subprocess.run(["bash", str(BUMP_SCRIPT), str(repo)], capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "a51_ws").mkdir()
    (tmp_path / "VERSION").write_text("0.1.0\n")
    (tmp_path / "x").write_text("x")
    git(tmp_path, "add", "x")
    git(tmp_path, "commit", "-q", "-m", "first")
    return tmp_path


def stamped(repo):
    return (repo / "a51_ws" / "_version.py").read_text().strip()


def test_stamp_uses_label_plus_commit_count_including_the_new_commit(repo):
    result = run_bump(repo)
    assert result.returncode == 0, result.stderr
    assert stamped(repo) == '__version__ = "0.1.0.2"'


def test_restamping_same_count_is_allowed(repo):
    run_bump(repo)
    assert run_bump(repo).returncode == 0


def test_lower_build_is_refused(repo):
    (repo / "a51_ws" / "_version.py").write_text('__version__ = "0.1.0.99"\n')
    result = run_bump(repo)
    assert result.returncode != 0
    assert "never go backwards" in result.stderr


def test_higher_build_but_lower_minor_is_refused(repo):
    # 0.2.0.1 is a LATER version than 0.1.0.999, so lowering the label must fail even though BUILD grows.
    (repo / "a51_ws" / "_version.py").write_text('__version__ = "0.2.0.1"\n')
    result = run_bump(repo)
    assert result.returncode != 0


def test_raising_minor_by_hand_is_accepted(repo):
    (repo / "a51_ws" / "_version.py").write_text('__version__ = "0.1.0.1"\n')
    (repo / "VERSION").write_text("0.2.0\n")
    assert run_bump(repo).returncode == 0
    assert stamped(repo) == '__version__ = "0.2.0.2"'


def test_shallow_clone_is_refused(repo, tmp_path_factory):
    shallow = tmp_path_factory.mktemp("shallow") / "clone"
    subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{repo}", str(shallow)], check=True)
    (shallow / "a51_ws").mkdir(exist_ok=True)
    result = run_bump(shallow)
    assert result.returncode != 0
    assert "shallow" in result.stderr
