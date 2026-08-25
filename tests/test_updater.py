import json

import updater


class Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps({
            "tag_name": "v0.2.0",
            "html_url": "https://example.test/release",
        }).encode()


def test_new_release_is_returned(monkeypatch):
    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    monkeypatch.setattr(updater, "CURRENT_VERSION", "0.1.0")
    result = updater.check_for_update()
    assert result["version"] == "0.2.0"
    assert result["url"] == updater.RELEASES_PAGE


def test_current_release_is_not_reported(monkeypatch):
    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    monkeypatch.setattr(updater, "CURRENT_VERSION", "0.2.0")
    assert updater.check_for_update() is None


def test_update_link_stays_on_project_releases_page(monkeypatch):
    class UnexpectedLinkResponse(Response):
        def read(self):
            return json.dumps({
                "tag_name": "v0.2.0",
                "html_url": "https://example.test/phishing",
            }).encode()

    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda *_args, **_kwargs: UnexpectedLinkResponse())
    monkeypatch.setattr(updater, "CURRENT_VERSION", "0.1.0")
    assert updater.check_for_update()["url"] == updater.RELEASES_PAGE
