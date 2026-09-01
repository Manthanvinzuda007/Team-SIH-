"""Phase 2/13: dataset-path configuration is env-based, not a hard-coded
Windows path, and missing/misconfigured directories are reported clearly
rather than silently ignored or crashing the app.
"""
import os

import pytest

from app.core.config import Settings, DatasetNotConfiguredError


def test_no_hardcoded_windows_path_in_default_settings():
    s = Settings(_env_file=None)
    assert "D:\\" not in s.DATASET_PATH if s.DATASET_PATH else True
    assert "D:\\" not in s.IAVNS_DATA_DIR
    assert "DHruvAI" not in s.IAVNS_DATA_DIR


def test_iavns_data_dir_env_var_is_honored(tmp_path, monkeypatch):
    monkeypatch.setenv("IAVNS_DATA_DIR", str(tmp_path))
    s = Settings(_env_file=None)
    assert str(s.dataset_dir) == str(tmp_path)


def test_relative_iavns_data_dir_resolves_against_backend_root():
    s = Settings(_env_file=None, IAVNS_DATA_DIR="./DataSets")
    assert s.dataset_dir.is_absolute()
    assert s.dataset_dir.name == "DataSets"


def test_validate_dataset_dir_reports_missing_directory(tmp_path):
    s = Settings(_env_file=None, IAVNS_DATA_DIR=str(tmp_path / "does_not_exist"))
    status = s.validate_dataset_dir()
    assert status.ok is False
    assert status.exists is False
    assert "does not exist" in status.message


def test_validate_dataset_dir_reports_empty_directory(tmp_path):
    s = Settings(_env_file=None, IAVNS_DATA_DIR=str(tmp_path))
    status = s.validate_dataset_dir()
    assert status.ok is False
    assert status.exists is True
    assert status.has_files is False
    assert "empty" in status.message


def test_validate_dataset_dir_ok_when_populated(tmp_path):
    (tmp_path / "placeholder.txt").write_text("x")
    s = Settings(_env_file=None, IAVNS_DATA_DIR=str(tmp_path))
    status = s.validate_dataset_dir()
    assert status.ok is True


def test_legacy_dataset_path_takes_priority_when_set(tmp_path):
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "f.txt").write_text("x")
    other = tmp_path / "other"
    other.mkdir()
    s = Settings(_env_file=None, DATASET_PATH=str(legacy), IAVNS_DATA_DIR=str(other))
    assert str(s.dataset_dir) == str(legacy)


def test_ensure_loaded_raises_clear_error_when_dataset_missing(tmp_path, monkeypatch):
    from app.core import config as config_module
    monkeypatch.setenv("IAVNS_DATA_DIR", str(tmp_path / "missing"))
    config_module.reset_settings_cache()
    try:
        from app.core import pipeline
        pipeline._state["loaded"] = False
        with pytest.raises(DatasetNotConfiguredError):
            pipeline.ensure_loaded()
    finally:
        config_module.reset_settings_cache()


def test_routes_optimize_returns_clear_503_when_dataset_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("IAVNS_DATA_DIR", str(tmp_path / "missing"))
    from app.core import config as config_module
    config_module.reset_settings_cache()
    try:
        from app.core import pipeline
        pipeline._state["loaded"] = False
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        body = {"origin": {"lat": -65, "lon": -60}, "destination": {"lat": -66, "lon": -62}}
        r = client.post("/api/routes/optimize", json=body)
        assert r.status_code == 503
        payload = r.json()
        assert payload["error"] is True
        assert payload["code"] == "DATASET_NOT_CONFIGURED"
    finally:
        config_module.reset_settings_cache()
