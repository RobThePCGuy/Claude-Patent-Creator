"""setup must not crash when stdin is not a TTY (issue #52).

setup_bigquery_auth_prompt() calls input(); in CI, agent-driven, or piped
contexts with no usable stdin that raises EOFError mid-setup. When stdin is
not interactive, setup must fall back to its existing --non-interactive path.
"""

from types import SimpleNamespace

from mcp_server import cli


def _args(non_interactive=False):
    return SimpleNamespace(non_interactive=non_interactive, rebuild=False, no_hyde=False)


def test_non_tty_stdin_forces_non_interactive(monkeypatch):
    monkeypatch.setattr(cli, "_stdin_is_interactive", lambda: False)
    args = _args()

    cli._normalize_interactivity(args)

    assert args.non_interactive is True


def test_tty_stdin_keeps_interactive(monkeypatch):
    monkeypatch.setattr(cli, "_stdin_is_interactive", lambda: True)
    args = _args()

    cli._normalize_interactivity(args)

    assert args.non_interactive is False


def test_explicit_flag_is_never_downgraded(monkeypatch):
    monkeypatch.setattr(cli, "_stdin_is_interactive", lambda: True)
    args = _args(non_interactive=True)

    cli._normalize_interactivity(args)

    assert args.non_interactive is True


def test_setup_command_wires_normalization():
    import inspect

    assert "_normalize_interactivity(" in inspect.getsource(cli.setup_command)
