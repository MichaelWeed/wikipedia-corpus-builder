import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from corpussieve.cli.main import app

runner = CliRunner()


def test_cli_model_detect_json() -> None:
    res = runner.invoke(app, ["model", "detect", "--json"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert isinstance(data, list)


def test_cli_model_add_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("corpussieve.models.config.get_config_dir", lambda: tmp_path)
    res = runner.invoke(
        app,
        [
            "model",
            "add",
            "--url",
            "http://127.0.0.1:11434",
            "--provider",
            "ollama",
            "--json",
        ],
    )
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data["status"] == "added"
    assert data["base_url"] == "http://127.0.0.1:11434"
