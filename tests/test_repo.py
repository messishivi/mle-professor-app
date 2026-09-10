from types import SimpleNamespace

import pytest

from repo import fetch_readme, parse_repo


def test_parse_github_urls():
    assert parse_repo("https://github.com/you/your-service") == (
        "github.com",
        "you",
        "your-service",
    )
    assert parse_repo("https://github.com/you/your-service.git")[2] == "your-service"
    assert parse_repo("github.com/you/your-service")[1:] == ("you", "your-service")
    assert parse_repo("git@github.com:you/your-service.git") == (
        "github.com",
        "you",
        "your-service",
    )
    assert parse_repo("https://github.com/you/your-service/tree/main")[2] == "your-service"


def test_parse_rejects_non_git_hosts():
    assert parse_repo("https://example.com/you/your-service") is None
    assert parse_repo("https://github.com/settings") is None
    assert parse_repo("not a url") is None
    assert parse_repo("") is None


def test_fetch_readme_uses_github_api(monkeypatch):
    calls = []

    def fake_get(url, headers=None):
        calls.append(url)
        if "api.github.com" in url:
            return SimpleNamespace(status_code=200, text="# Rec service\n\nTwo-tower ranker.\n")
        return SimpleNamespace(status_code=404, text="")

    doc = fetch_readme("https://github.com/you/rec-service", get=fake_get)
    assert "api.github.com/repos/you/rec-service/readme" in calls[0]
    assert "Two-tower ranker" in doc.content
    assert doc.url == "https://github.com/you/rec-service"
    assert "readme" in doc.readme_url.lower()


def test_fetch_readme_falls_back_to_raw():
    def fake_get(url, headers=None):
        if "raw.githubusercontent.com" in url and url.endswith("README.md"):
            return SimpleNamespace(status_code=200, text="# shipped modules\n")
        return SimpleNamespace(status_code=404, text="")

    doc = fetch_readme("https://github.com/you/rec-service", get=fake_get)
    assert "shipped modules" in doc.content


def test_fetch_readme_rejects_bad_url():
    with pytest.raises(ValueError, match="GitHub or GitLab"):
        fetch_readme("https://evil.example/x")
