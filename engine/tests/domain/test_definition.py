from pathlib import Path

import pytest
from typer.testing import CliRunner

from corpussieve.cli.main import app
from corpussieve.contracts.domain import DomainDefinition, DomainRoot
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.domain.definition import domain_hash, load_domain, save_domain

runner = CliRunner()


def test_load_save_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "test-domain.yaml"
    defn = DomainDefinition(
        id="video-games",
        name="Video Games",
        language="en",
        description="Test domain",
        roots=[DomainRoot(query="Category:Video games")],
    )
    save_domain(defn, path)
    assert path.exists()

    loaded = load_domain(path)
    assert loaded.id == defn.id
    assert loaded.name == defn.name
    assert loaded.language == defn.language


def test_invalid_yaml_error(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("id: [unclosed list", encoding="utf-8")

    with pytest.raises(CorpusSieveError) as exc_info:
        load_domain(bad_yaml)
    assert exc_info.value.code == ErrorCode.INTERNAL_ERROR


def test_domain_hash_stability() -> None:
    defn1 = DomainDefinition(
        id="vg",
        name="Video Games",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games")],
    )
    defn2 = DomainDefinition(
        name="Video Games",
        id="vg",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Video games")],
    )
    assert domain_hash(defn1) == domain_hash(defn2)


def test_cli_domain_create_then_load(tmp_path: Path) -> None:
    res = runner.invoke(
        app,
        [
            "domain",
            "create",
            "--id",
            "retrogaming",
            "--name",
            "Retro Gaming",
            "--language",
            "en",
            "--project-dir",
            str(tmp_path),
            "--intent",
            "Classic 8-bit games",
            "--json",
        ],
    )
    assert res.exit_code == 0
    domain_file = tmp_path / "domains" / "retrogaming.yaml"
    assert domain_file.exists()

    loaded = load_domain(domain_file)
    assert loaded.id == "retrogaming"
    assert loaded.name == "Retro Gaming"
    assert loaded.description == "Classic 8-bit games"
