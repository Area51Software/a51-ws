"""Save and restore against a fake iTerm2 (no real iTerm2 needed)."""
import pytest

import fake_iterm2
from a51_ws import cli, store
from a51_ws.store import WorkspaceError
from conftest import pane


@pytest.fixture(autouse=True)
def use_fake_iterm2(monkeypatch):
    monkeypatch.setattr(cli, "iterm2", fake_iterm2)
    fake_iterm2.Window.created = []
    fake_iterm2.Window.created_windows = []
    fake_iterm2.Window.fail_on_creation_number = None
    fake_iterm2.set_open_windows([])


def open_window_with_split(claude_folder="/work/a", other_folder="/work/b"):
    claude_pane = fake_iterm2.Session(path=claude_folder, job="claude")
    other_pane = fake_iterm2.Session(path=other_folder, job="zsh")
    return fake_iterm2.Window([fake_iterm2.Tab(fake_iterm2.Splitter([claude_pane, other_pane]))])


def test_save_records_folders_claude_marker_and_only_appearance(isolated_workspaces_folder, capsys):
    fake_iterm2.set_open_windows([open_window_with_split()])
    cli.main(["save", "work"])
    saved = store.load_workspace("work")
    left, right = saved["windows"][0]["tabs"][0]["children"]
    assert (left["folder"], left["runs_claude"], right["runs_claude"]) == ("/work/a", True, False)
    assert left["appearance"] == {"Normal Font": "Monaco 21"}  # "Name" is not appearance
    assert "Saved 'work'" in capsys.readouterr().out


def test_save_with_no_windows_open_saves_nothing(isolated_workspaces_folder, capsys):
    assert cli.main(["save", "work"]) == 1
    assert "No iTerm2 windows are open" in capsys.readouterr().err
    assert not (isolated_workspaces_folder / "work.json").exists()


def test_save_over_existing_says_replaced(isolated_workspaces_folder, capsys):
    fake_iterm2.set_open_windows([open_window_with_split()])
    cli.main(["save", "work"])
    cli.main(["save", "--yes", "work"])
    assert "Replaced 'work'" in capsys.readouterr().out


def test_restore_rebuilds_windows_tabs_splits_and_restarts_only_claude(
        isolated_workspaces_folder, tmp_path, capsys):
    folder_a, folder_b, folder_c = (tmp_path / n for n in "abc")
    for folder in (folder_a, folder_b, folder_c):
        folder.mkdir()
    store.save_workspace_file("work", [{"frame": [5, 6, 700, 500], "tabs": [
        {"type": "split", "side_by_side": True,
         "children": [pane(str(folder_a), runs_claude=True), pane(str(folder_b))]},
        pane(str(folder_c)),
    ]}])
    assert cli.main(["up", "work"]) == 0
    assert len(fake_iterm2.Window.created) == 1
    assert fake_iterm2.Window.created[0].directory == str(folder_a)
    assert "Claude restarted in 1 pane(s)" in capsys.readouterr().out


def test_restore_sends_claude_command_and_nothing_else(isolated_workspaces_folder, tmp_path, monkeypatch):
    sent = []
    original = fake_iterm2.Session.async_send_text

    async def record(self, text):
        sent.append(text)
        await original(self, text)
    monkeypatch.setattr(fake_iterm2.Session, "async_send_text", record)
    store.save_workspace_file("work", [{"tabs": [pane(str(tmp_path), runs_claude=True),
                                                 pane(str(tmp_path))]}])
    cli.main(["up", "work"])
    assert sent == ["claude --continue || claude\n"]


def test_restore_warns_about_missing_folders_and_still_opens_the_pane(
        isolated_workspaces_folder, capsys):
    store.save_workspace_file("work", [{"tabs": [pane("/definitely/not/here")]}])
    assert cli.main(["up", "work"]) == 0
    assert "/definitely/not/here no longer exists" in capsys.readouterr().err
    assert fake_iterm2.Window.created[0].directory is None  # fell back to the default folder


def test_one_failing_window_does_not_lose_the_others(isolated_workspaces_folder, tmp_path, capsys):
    store.save_workspace_file("work", [{"tabs": [pane(str(tmp_path))]},
                                       {"tabs": [pane(str(tmp_path))]}])
    fake_iterm2.Window.fail_on_creation_number = 1
    assert cli.main(["up", "work"]) == 1
    captured = capsys.readouterr()
    assert "window 1 could not be restored" in captured.err
    assert "1 of 2 window(s) could not be restored" in captured.err
    assert len(fake_iterm2.Window.created) == 2  # window 2 was still attempted


def test_unknown_appearance_setting_is_skipped_not_fatal(tmp_path):
    customization = cli.folder_customization(
        {"folder": str(tmp_path), "appearance": {"Unknown Setting": 1, "Normal Font": "Monaco 21"}})
    assert customization.settings == {"Normal Font": "Monaco 21"}


def test_up_for_unknown_workspace_is_a_clean_error(isolated_workspaces_folder, capsys):
    assert cli.main(["up", "nope"]) == 1
    assert "No saved workspace called 'nope'" in capsys.readouterr().err


def test_iterm2_unreachable_gives_plain_english_help(isolated_workspaces_folder, monkeypatch, capsys):
    def refuse(action, retry=False):
        raise ConnectionRefusedError("[Errno 61] Connection refused")
    monkeypatch.setattr(fake_iterm2, "run_until_complete", refuse)
    assert cli.main(["save", "work"]) == 1
    error_text = capsys.readouterr().err
    assert "Enable Python API" in error_text and "Traceback" not in error_text


def test_debug_variable_shows_the_real_traceback(isolated_workspaces_folder, monkeypatch):
    def refuse(action, retry=False):
        raise ConnectionRefusedError("boom")
    monkeypatch.setattr(fake_iterm2, "run_until_complete", refuse)
    monkeypatch.setenv("A51_WS_DEBUG", "1")
    with pytest.raises(ConnectionRefusedError):
        cli.main(["save", "work"])


# ---- tab titles

def test_save_records_tab_titles_you_set_and_none_for_automatic_ones(isolated_workspaces_folder):
    titled = fake_iterm2.Tab(fake_iterm2.Session(path="/work/a"), title_override="MYPROJECT")
    untitled = fake_iterm2.Tab(fake_iterm2.Session(path="/work/b"), title_override="")
    fake_iterm2.set_open_windows([fake_iterm2.Window([titled, untitled])])
    cli.main(["save", "work"])
    first_tab, second_tab = store.load_workspace("work")["windows"][0]["tabs"]
    assert first_tab["tab_title"] == "MYPROJECT"
    assert second_tab["tab_title"] is None


def test_restore_puts_saved_titles_back_on_the_new_tabs(isolated_workspaces_folder, tmp_path):
    first = {**pane(str(tmp_path)), "tab_title": "BUILDS"}
    second = {**pane(str(tmp_path)), "tab_title": "SERVICES-DASH"}
    third = pane(str(tmp_path))  # a workspace saved before titles existed, or an untitled tab
    store.save_workspace_file("work", [{"tabs": [first, second, third]}])
    assert cli.main(["up", "work"]) == 0
    titles = [tab.title_override for tab in fake_iterm2.Window.created_windows[0].tabs]
    assert titles == ["BUILDS", "SERVICES-DASH", ""]


def test_title_that_cannot_be_set_warns_but_the_tab_still_restores(
        isolated_workspaces_folder, tmp_path, monkeypatch, capsys):
    async def refuse(self, title):
        raise RuntimeError("simulated iTerm2 refusal")
    monkeypatch.setattr(fake_iterm2.Tab, "async_set_title", refuse)
    store.save_workspace_file("work", [{"tabs": [{**pane(str(tmp_path)), "tab_title": "BUILDS"}]}])
    assert cli.main(["up", "work"]) == 0
    assert "title 'BUILDS' could not be set" in capsys.readouterr().err
    assert len(fake_iterm2.Window.created_windows[0].tabs) == 1


def test_titles_survive_a_full_save_then_restore_round_trip(isolated_workspaces_folder, tmp_path):
    root = fake_iterm2.Session(path=str(tmp_path))
    fake_iterm2.set_open_windows([fake_iterm2.Window([
        fake_iterm2.Tab(root, title_override="a51-ws")])])
    cli.main(["save", "work"])
    cli.main(["up", "work"])
    assert fake_iterm2.Window.created_windows[0].tabs[0].title_override == "a51-ws"


# ---- overwrite safety check

@pytest.fixture
def existing_work_workspace(isolated_workspaces_folder):
    fake_iterm2.set_open_windows([open_window_with_split("/old/a", "/old/b")])
    cli.main(["save", "work"])  # first save: name is new, so no question is asked
    fake_iterm2.set_open_windows([open_window_with_split("/new/a", "/new/b")])
    return isolated_workspaces_folder


def saved_folder():
    return store.load_workspace("work")["windows"][0]["tabs"][0]["children"][0]["folder"]


def answer_with(monkeypatch, *answers, interactive=True):
    questions = []
    given = iter(answers)

    def fake_read_answer(question):
        questions.append(question)
        return next(given)
    monkeypatch.setattr(cli, "read_answer", fake_read_answer)
    monkeypatch.setattr(cli, "input_is_interactive", lambda: interactive)
    return questions


def test_saving_a_new_name_asks_nothing(isolated_workspaces_folder, monkeypatch):
    questions = answer_with(monkeypatch)
    fake_iterm2.set_open_windows([open_window_with_split()])
    assert cli.main(["save", "brand-new"]) == 0
    assert questions == []


@pytest.mark.parametrize("answer", ["y", "Y", "yes", "YES", " yes "])
def test_yes_overwrites(existing_work_workspace, monkeypatch, answer):
    questions = answer_with(monkeypatch, answer)
    assert cli.main(["save", "work"]) == 0
    assert saved_folder() == "/new/a"
    assert questions == ["Workspace 'work' already exists. Overwrite it? [y/N] "]


@pytest.mark.parametrize("answer", ["n", "no", "", "maybe", "yep"])
def test_anything_but_yes_keeps_the_old_workspace(existing_work_workspace, monkeypatch, capsys, answer):
    answer_with(monkeypatch, answer)
    assert cli.main(["save", "work"]) == 1
    assert saved_folder() == "/old/a"
    assert "Not saved" in capsys.readouterr().err


def test_end_of_input_counts_as_no(existing_work_workspace, monkeypatch):
    def end_of_input(question):
        raise EOFError
    monkeypatch.setattr(cli, "read_answer", end_of_input)
    monkeypatch.setattr(cli, "input_is_interactive", lambda: True)
    assert cli.main(["save", "work"]) == 1
    assert saved_folder() == "/old/a"


def test_without_a_terminal_it_refuses_instead_of_waiting_forever(
        existing_work_workspace, monkeypatch, capsys):
    questions = answer_with(monkeypatch, interactive=False)
    assert cli.main(["save", "work"]) == 1
    assert questions == [] and saved_folder() == "/old/a"
    assert "--yes" in capsys.readouterr().err


@pytest.mark.parametrize("flag", ["--yes", "-y"])
def test_yes_flag_skips_the_question(existing_work_workspace, monkeypatch, flag):
    questions = answer_with(monkeypatch, interactive=False)
    assert cli.main(["save", flag, "work"]) == 0
    assert questions == [] and saved_folder() == "/new/a"


def test_yes_flag_also_works_after_the_name(existing_work_workspace, monkeypatch):
    answer_with(monkeypatch, interactive=False)
    assert cli.main(["save", "work", "--yes"]) == 0


def test_yes_flag_is_only_for_save(isolated_workspaces_folder, capsys):
    assert cli.main(["list", "--yes"]) == 2


def test_name_that_differs_only_by_case_is_refused_even_with_yes(existing_work_workspace, capsys):
    assert cli.main(["save", "--yes", "Work"]) == 1
    assert "differs only by capital letters from 'work'" in capsys.readouterr().err
    assert saved_folder() == "/old/a"


def test_the_question_comes_before_any_iterm2_work(existing_work_workspace, monkeypatch):
    answer_with(monkeypatch, "n")
    reached_iterm2 = []
    monkeypatch.setattr(fake_iterm2, "run_until_complete", lambda *a, **k: reached_iterm2.append(1))
    cli.main(["save", "work"])
    assert reached_iterm2 == []
