"""Tests for the central configuration schema and file-backed store."""

import importlib

import pytest

from mcp_server import config as cfg


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Point the config store at a temp dir and clear relevant env vars."""
    monkeypatch.setenv("PATENT_CONFIG_DIR", str(tmp_path))
    for opt in cfg.OPTIONS:
        monkeypatch.delenv(opt.key, raising=False)
    yield


class TestSchema:
    def test_every_option_is_well_formed(self):
        for opt in cfg.OPTIONS:
            assert opt.key and opt.label and opt.description and opt.section
            assert opt.type in {"str", "int", "bool", "choice", "secret"}
            if opt.type == "choice":
                assert opt.choices, f"{opt.key} is a choice with no choices"
                # A non-empty default must be one of the choices.
                if opt.default:
                    assert opt.default in opt.choices
            if opt.type == "bool":
                assert opt.default in {"true", "false"}

    def test_keys_are_unique(self):
        keys = [o.key for o in cfg.OPTIONS]
        assert len(keys) == len(set(keys))


class TestValidate:
    def test_int_rejects_non_int_and_below_min(self):
        key = "PATENT_BIGQUERY_MAX_BYTES_BILLED"
        assert cfg.validate(key, "abc") is not None
        assert cfg.validate(key, "1") is not None  # below 1 GiB minimum
        assert cfg.validate(key, str(250 * cfg.GIB)) is None

    def test_choice_rejects_unknown(self):
        assert cfg.validate("PATENT_LOG_LEVEL", "LOUD") is not None
        assert cfg.validate("PATENT_LOG_LEVEL", "DEBUG") is None

    def test_bool_accepts_common_forms(self):
        for good in ("true", "false", "yes", "no", "1", "0"):
            assert cfg.validate("FORCE_CPU", good) is None
        assert cfg.validate("FORCE_CPU", "maybe") is not None

    def test_unknown_key(self):
        assert cfg.validate("NOPE", "x") is not None


class TestNormalize:
    def test_bool_canonicalized(self):
        assert cfg.normalize("FORCE_CPU", "yes") == "true"
        assert cfg.normalize("FORCE_CPU", "0") == "false"

    def test_non_bool_passthrough(self):
        assert cfg.normalize("GOOGLE_CLOUD_PROJECT", "my-proj") == "my-proj"


class TestStoreRoundTrip:
    def test_save_then_load(self):
        cfg.save_value("GOOGLE_CLOUD_PROJECT", "proj-123")
        assert cfg.load_file()["GOOGLE_CLOUD_PROJECT"] == "proj-123"

    def test_unknown_key_rejected_on_save(self):
        with pytest.raises(KeyError):
            cfg.save_value("NOT_A_SETTING", "x")

    def test_unset_removes_key(self):
        cfg.save_value("FORCE_CPU", "true")
        cfg.unset_value("FORCE_CPU")
        assert "FORCE_CPU" not in cfg.load_file()

    def test_blank_values_not_persisted(self):
        cfg.save_value("GOOGLE_CLOUD_PROJECT", "")
        assert "GOOGLE_CLOUD_PROJECT" not in cfg.load_file()


class TestPrecedence:
    def test_default_then_file_then_env(self, monkeypatch):
        key = "PATENT_LOG_LEVEL"
        assert cfg.get_effective(key) == ("INFO", "default")

        cfg.save_value(key, "WARNING")
        assert cfg.get_effective(key) == ("WARNING", "file")

        monkeypatch.setenv(key, "ERROR")
        assert cfg.get_effective(key) == ("ERROR", "env")

    def test_empty_env_is_treated_as_unset(self, monkeypatch):
        key = "GOOGLE_CLOUD_PROJECT"
        cfg.save_value(key, "from-file")
        monkeypatch.setenv(key, "")
        assert cfg.get_effective(key) == ("from-file", "file")


class TestApplyToEnv:
    def test_bridges_file_into_env_when_unset(self, monkeypatch):
        cfg.save_value("PATENT_LOG_LEVEL", "DEBUG")
        monkeypatch.delenv("PATENT_LOG_LEVEL", raising=False)
        cfg.apply_config_to_env()
        import os

        assert os.environ["PATENT_LOG_LEVEL"] == "DEBUG"

    def test_does_not_override_real_env(self, monkeypatch):
        cfg.save_value("PATENT_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("PATENT_LOG_LEVEL", "ERROR")
        cfg.apply_config_to_env()
        import os

        assert os.environ["PATENT_LOG_LEVEL"] == "ERROR"


def test_module_reimport_is_stable():
    """Re-importing config must not raise (schema is module-level)."""
    importlib.reload(cfg)
