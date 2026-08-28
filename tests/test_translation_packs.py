import json
import zipfile

import pytest

from translation_packs import PackError, PackManager


def write_pack(root, name="Custom English", author="Tester", files=("MainMenu.txt",)):
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(json.dumps({"Name": name, "Authors": [author]}), encoding="utf-8")
    for filename in files:
        (root / filename).write_text("translated", encoding="utf-8")


def test_imports_folder_and_persists_pack(tmp_path):
    source = tmp_path / "source"; write_pack(source)
    manager = PackManager(tmp_path / "app", tmp_path / "Translations")

    record = manager.import_path(source)

    assert record["name"] == "Custom English"
    assert (tmp_path / "Translations" / "source" / "manifest.json").is_file()
    assert manager.load()["packs"][0]["id"] == record["id"]


def test_imports_zip_with_outer_folder(tmp_path):
    source = tmp_path / "Pack"; write_pack(source, files=("MainMenu.txt", "Teams.txt"))
    archive = tmp_path / "pack.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        for path in source.rglob("*"):
            zipped.write(path, path.relative_to(tmp_path))
    manager = PackManager(tmp_path / "app", tmp_path / "Translations")

    record = manager.import_path(archive)

    assert record["name"] == "Custom English"
    assert (tmp_path / "Translations" / "Pack" / "Teams.txt").read_text(encoding="utf-8") == "translated"


def test_replacement_makes_backup_and_restore_recovers_old_pack(tmp_path):
    translations = tmp_path / "Translations"
    old = tmp_path / "old"; write_pack(old, name="Same", files=("MainMenu.txt",)); (old / "MainMenu.txt").write_text("old", encoding="utf-8")
    manager = PackManager(tmp_path / "app", translations)
    first = manager.import_path(old)
    new = tmp_path / "new"; write_pack(new, name="Same", files=("MainMenu.txt",)); (new / "MainMenu.txt").write_text("new", encoding="utf-8")

    manager.import_path(new)

    assert (translations / first["folder"] / "MainMenu.txt").read_text(encoding="utf-8") == "new"
    assert manager.restore(first["id"])
    assert (translations / first["folder"] / "MainMenu.txt").read_text(encoding="utf-8") == "old"


def test_only_one_custom_pack_is_active_and_default_deactivates(tmp_path):
    manager = PackManager(tmp_path / "app", tmp_path / "Translations")
    first_dir = tmp_path / "one"; write_pack(first_dir, name="One")
    second_dir = tmp_path / "two"; write_pack(second_dir, name="Two")
    first = manager.import_path(first_dir); second = manager.import_path(second_dir)

    assert manager.activate(first["id"])["active_pack"] == first["id"]
    assert manager.activate(second["id"])["active_pack"] == second["id"]
    assert manager.deactivate()["active_pack"] is None


def test_rejects_missing_manifest_and_translation_files(tmp_path):
    manager = PackManager(tmp_path / "app", tmp_path / "Translations")
    missing_manifest = tmp_path / "bad"; missing_manifest.mkdir()
    with pytest.raises(PackError, match="manifest"):
        manager.import_path(missing_manifest)
    missing_txt = tmp_path / "also-bad"; write_pack(missing_txt, files=())
    with pytest.raises(PackError, match="translation"):
        manager.import_path(missing_txt)


def test_does_not_overwrite_unmanaged_translation_folder(tmp_path):
    translations = tmp_path / "Translations"; official = translations / "en"; official.mkdir(parents=True)
    (official / "manifest.json").write_text(json.dumps({"Name": "English", "Authors": ["Northwood"]}), encoding="utf-8")
    (official / "MainMenu.txt").write_text("official", encoding="utf-8")
    source = tmp_path / "en"; write_pack(source, name="Custom English")
    manager = PackManager(tmp_path / "app", translations)

    record = manager.import_path(source)

    assert record["folder"] == "en-custom"
    assert (official / "MainMenu.txt").read_text(encoding="utf-8") == "official"


def test_resolves_github_repository_and_direct_zip(monkeypatch, tmp_path):
    manager = PackManager(tmp_path / "app", tmp_path / "Translations")
    assert manager.resolve_link("https://github.com/example/pack") == "https://api.github.com/repos/example/pack/zipball"
    assert manager.resolve_link("https://example.test/custom.zip") == "https://example.test/custom.zip"


def test_import_records_source_url(tmp_path):
    source = tmp_path / "pack"; write_pack(source)
    manager = PackManager(tmp_path / "app", tmp_path / "Translations")

    record = manager.import_path(source, source_url="https://github.com/example/pack")

    assert record["source"] == "https://github.com/example/pack"
    assert manager.load()["packs"][0]["source"] == record["source"]


def test_github_search_uses_api_results(monkeypatch, tmp_path):
    manager = PackManager(tmp_path / "app", tmp_path / "Translations")
    payload = {"items": [{"full_name": "example/pack", "html_url": "https://github.com/example/pack", "description": "translation", "updated_at": "2026-01-01T00:00:00Z", "stargazers_count": 2}]}
    monkeypatch.setattr(manager, "_read_url", lambda url: json.dumps(payload).encode())

    results = manager.search_github("SCP SL translation")

    assert results[0]["full_name"] == "example/pack"
