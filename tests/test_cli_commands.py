import pytest

from a51_ws import cli, store


def test_no_arguments_and_help_print_usage_and_succeed(capsys):
    assert cli.main([]) == 0
    assert cli.main(["--help"]) == 0
    assert capsys.readouterr().out.count("a51-ws save [-y] [NAME]") == 2


def test_version_flag_prints_full_version(capsys):
    assert cli.main(["--version"]) == 0
    assert capsys.readouterr().out.startswith("a51-ws 0.1.0.")


@pytest.mark.parametrize("arguments", [["frobnicate"], ["save", "a", "b"], ["list", "x", "y"]])
def test_wrong_usage_exits_2_with_usage_on_stderr(arguments, capsys):
    assert cli.main(arguments) == 2
    assert "unknown or malformed command" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["show", "rm"])
def test_show_and_rm_require_an_explicit_name(command, isolated_workspaces_folder, capsys):
    """`a51-ws rm` must never silently delete the default 'last' workspace."""
    store.save_workspace_file("last", [{"tabs": [{"type": "pane"}]}])
    assert cli.main([command]) == 1
    assert "needs a workspace name" in capsys.readouterr().err
    assert (isolated_workspaces_folder / "last.json").exists()


def test_rm_unknown_workspace_is_an_error_not_a_false_success(isolated_workspaces_folder, capsys):
    assert cli.main(["rm", "ghost"]) == 1
    assert "No saved workspace called 'ghost'" in capsys.readouterr().err


def test_unsafe_name_is_refused_before_touching_the_disk(isolated_workspaces_folder, capsys):
    assert cli.main(["rm", "../../etc/passwd"]) == 1
    assert "not a usable workspace name" in capsys.readouterr().err


def test_list_and_show_and_rm_flow(isolated_workspaces_folder, sample_windows, capsys):
    store.save_workspace_file("work", sample_windows)
    assert cli.main(["list"]) == 0
    listing = capsys.readouterr().out
    assert "work" in listing and "2 tab(s)" in listing
    assert cli.main(["show", "work"]) == 0
    tree = capsys.readouterr().out
    assert "- /work/a  [claude]" in tree and "+ side by side" in tree and "- /work/c" in tree
    assert cli.main(["rm", "work"]) == 0
    assert cli.main(["list"]) == 0
    assert "No saved workspaces yet" in capsys.readouterr().out


def test_list_marks_a_damaged_file_instead_of_crashing(isolated_workspaces_folder, capsys):
    (isolated_workspaces_folder / "broken.json").write_text("{nope")
    assert cli.main(["list"]) == 0
    assert "UNREADABLE" in capsys.readouterr().out


def test_show_a_damaged_file_explains_the_problem(isolated_workspaces_folder, capsys):
    (isolated_workspaces_folder / "broken.json").write_text("{nope")
    assert cli.main(["show", "broken"]) == 1
    assert "not valid JSON" in capsys.readouterr().err


def test_show_prints_each_tab_title(isolated_workspaces_folder, capsys):
    store.save_workspace_file("work", [{"tabs": [
        {"type": "pane", "folder": "/a", "tab_title": "BUILDS"},
        {"type": "pane", "folder": "/b", "tab_title": None}]}])
    assert cli.main(["show", "work"]) == 0
    output = capsys.readouterr().out
    assert 'Tab 1  "BUILDS"' in output
    assert "Tab 2\n" in output
