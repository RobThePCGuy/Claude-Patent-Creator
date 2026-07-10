"""setup must attempt to provision system Graphviz.

A fresh install shipped with all four diagram tools dead: the Python
graphviz package was present but the system binary was not, and setup never
ran the installer the repo already ships (graphviz_installer.ensure_graphviz).
The step is best-effort: failure prints guidance and never blocks setup.
"""

from mcp_server import cli


def test_setup_graphviz_reports_success():
    ready = cli._setup_graphviz(ensure_fn=lambda: (True, "Graphviz 14.1.2 ready"))
    assert ready is True


def test_setup_graphviz_failure_is_nonfatal():
    ready = cli._setup_graphviz(ensure_fn=lambda: (False, "no package manager found"))
    assert ready is False


def test_setup_graphviz_survives_installer_crash():
    def boom():
        raise RuntimeError("installer exploded")

    ready = cli._setup_graphviz(ensure_fn=boom)
    assert ready is False


def test_setup_command_wires_graphviz_step():
    """The step must actually be reachable from setup_command."""
    import inspect

    assert "_setup_graphviz(" in inspect.getsource(cli.setup_command)
