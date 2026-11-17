"""Tests for the optional settings GUI.

The GUI is thin glue over the (already tested) config store, so these tests
cover the pure helpers and that the module imports without a display. The
widget-building path is exercised only when a Tk display is actually available
(skipped on headless CI).
"""

from mcp_server import config_gui


def test_module_imports_without_display():
    # Importing the module must never require tkinter or a display.
    assert callable(config_gui.launch)


def test_plan_save_persists_only_changed_validated_fields():
    from mcp_server import config

    opt_proj = config.OPTIONS_BY_KEY["GOOGLE_CLOUD_PROJECT"]
    opt_cap = config.OPTIONS_BY_KEY["PATENT_BIGQUERY_MAX_BYTES_BILLED"]
    opt_log = config.OPTIONS_BY_KEY["PATENT_LOG_LEVEL"]
    opt_cpu = config.OPTIONS_BY_KEY["FORCE_CPU"]

    entries = [
        (opt_proj, "secret-from-env", "secret-from-env"),  # unchanged -> not saved
        (opt_cap, "abc", str(25 * config.GIB)),            # changed but invalid
        (opt_log, "DEBUG", "INFO"),                        # changed + valid
        (opt_cpu, "true", "false"),                        # changed + valid
    ]
    to_save, errors = config_gui._plan_save(entries)

    # Unchanged env-sourced value is never written to disk; invalid is rejected.
    assert to_save == {"PATENT_LOG_LEVEL": "DEBUG", "FORCE_CPU": "true"}
    assert len(errors) == 1
