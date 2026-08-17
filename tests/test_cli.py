"""The `jointview` command — the argv it builds, not the server it starts.

`subprocess.call` is patched out throughout, so these assert on the command line
handed to marimo. That is the whole of the CLI's job: everything after it belongs to
marimo and to the notebook.
"""

import runpy
import sys

import pytest

from jointview import cli


@pytest.fixture
def command(monkeypatch):
    """Run main() without starting a server, and hand back the argv it would have used."""
    seen = []

    def fake_call(argv):
        """Stand in for subprocess.call, recording the command instead of running it."""
        seen.append(argv)
        return 0

    monkeypatch.setattr(cli.subprocess, "call", fake_call)

    def run(*args):
        """Invoke the CLI with ``args`` and return the argv it assembled."""
        assert cli.main(list(args)) == 0
        return seen[-1]

    return run


@pytest.fixture
def navs(tmp_path):
    """A real parquet on disk, since the CLI checks the file exists before launching."""
    from jointview.data import demo_frame

    file = tmp_path / "navs.parquet"
    demo_frame(rows=20).write_parquet(file)
    return file


def test_the_notebook_is_packaged_next_to_the_cli():
    """`uvx jointview` only works if the notebook is in the wheel."""
    assert cli.APP.exists()


def test_it_runs_the_packaged_notebook_on_this_interpreter(command):
    """`python -m marimo`, because under uvx a bare `marimo` need not be the same env."""
    assert command() == [sys.executable, "-m", "marimo", "run", str(cli.APP)]


def test_no_data_means_no_arguments_for_the_notebook(command):
    """Nothing after the `--`, so the notebook falls back to the demo frame."""
    assert "--" not in command()


def test_edit_opens_the_notebook_instead(command):
    """The one flag that changes the marimo subcommand rather than the notebook's args."""
    assert "edit" in command("--edit")
    assert "run" not in command("--edit")


def test_data_reaches_the_notebook_behind_the_separator(command, navs):
    """The notebook reads its options off mo.cli_args(), which is what follows the `--`."""
    argv = command(str(navs))
    assert argv[-3:] == ["--", "--data", str(navs)]


def test_a_relative_path_is_resolved_against_the_shell(command, navs, monkeypatch):
    """The notebook lives in the installed wheel, not where the user is standing."""
    monkeypatch.chdir(navs.parent)
    assert command(navs.name)[-1] == str(navs)


def test_the_old_data_flag_still_works(command, navs):
    """--data is a hidden alias of the positional, kept so the old README line runs."""
    assert command("--data", str(navs))[-1] == str(navs)


def test_both_spellings_of_the_data_file_is_an_error(capsys, navs):
    """An alias that quietly beat the positional would open the wrong file, silently.

    The flag is hidden, so nobody types both on purpose: they are unsure which spelling
    this version reads. Naming both paths answers that; picking one would not.
    """
    with pytest.raises(SystemExit) as error:
        cli.main([str(navs), "--data", "other.parquet"])
    assert error.value.code == 2
    message = capsys.readouterr().err
    assert str(navs) in message
    assert "other.parquet" in message


def test_height_is_passed_on(command):
    """The plot height is the one thing the page cannot work out for itself."""
    assert command("--height", "900")[-2:] == ["--height", "900"]


def test_marimo_arguments_go_in_front_of_the_notebook(command):
    """`marimo run [OPTIONS] NAME`: behind the path they would be the notebook's."""
    argv = command("--", "--port", "8080", "--headless")
    assert argv[-4:] == ["--port", "8080", "--headless", str(cli.APP)]


def test_a_marimo_flags_value_is_not_mistaken_for_the_data_file(command):
    """`--port 8080` used to lose its 8080 to the optional positional.

    The notebook was then asked to read a file called 8080, and marimo got a bare
    `--port` — an error naming a flag the user never typed.
    """
    assert "--data" not in command("--", "--port", "8080")


def test_an_unknown_flag_on_our_side_is_an_error(command):
    """Before the `--` the parser is strict, so a typo is caught here and not by marimo."""
    with pytest.raises(SystemExit) as error:
        cli.main(["--nonsense"])
    assert error.value.code == 2


def test_a_missing_file_fails_before_anything_is_started(monkeypatch, tmp_path):
    """A bad path should be a line from the shell, not a traceback in an open browser tab."""

    def fail(argv):  # pragma: no cover - the point is that it is never reached
        """Fail the test if the CLI tries to launch marimo at all."""
        raise AssertionError("marimo should not have been started")  # noqa: TRY003

    monkeypatch.setattr(cli.subprocess, "call", fail)
    with pytest.raises(SystemExit) as error:
        cli.main([str(tmp_path / "absent.parquet")])
    assert error.value.code == 2


def test_the_exit_code_is_marimos(monkeypatch):
    """The wrapper is transparent: whatever marimo exits with is what the shell sees."""
    monkeypatch.setattr(cli.subprocess, "call", lambda argv: 3)
    assert cli.main([]) == 3


def test_ctrl_c_is_not_a_traceback(monkeypatch):
    """Ctrl-C reaches the child too, so there is nothing left to report."""

    def interrupt(argv):
        """Stand in for a subprocess.call interrupted from the terminal."""
        raise KeyboardInterrupt

    monkeypatch.setattr(cli.subprocess, "call", interrupt)
    assert cli.main([]) == 130


def test_python_m_jointview_is_the_same_entry_point(monkeypatch):
    """`python -m jointview` exits with what main() returned, and adds nothing of its own."""
    monkeypatch.setattr(cli, "main", lambda: 7)
    with pytest.raises(SystemExit) as error:
        runpy.run_module("jointview", run_name="__main__")
    assert error.value.code == 7
