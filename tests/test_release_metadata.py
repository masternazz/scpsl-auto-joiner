from pathlib import Path

import updater
import web_api


ROOT = Path(__file__).resolve().parents[1]


def test_release_version_fallbacks_stay_in_sync():
    assert web_api.APP_VERSION == updater.CURRENT_VERSION
    version = web_api.APP_VERSION
    assert f'else {{ "{version}" }}' in (ROOT / "build_release.ps1").read_text(encoding="utf-8")
    assert f"state.version||'{version}'" in (ROOT / "webui" / "app.js").read_text(encoding="utf-8")
    assert f"v{version}" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_takeover_documents_and_dev_dependencies_are_present():
    required = (
        "requirements-dev.txt",
        "docs/index.md",
        "docs/handoff.md",
        "docs/development.md",
        "docs/release-process.md",
        "docs/private-server-acceptance.md",
        ".github/workflows/ci.yml",
    )
    assert all((ROOT / path).is_file() for path in required)
