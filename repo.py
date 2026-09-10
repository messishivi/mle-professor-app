"""Fetch a public GitHub/GitLab README to ground Apply / delta analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote, urlparse

import requests

USER_AGENT = "mle-professor/0.1 (personal ML knowledge base)"
MAX_README_CHARS = 6000
TIMEOUT = 12
ALLOWED_HOSTS = frozenset({"github.com", "gitlab.com"})
BLOCKED_OWNERS = frozenset(
    {
        "about",
        "blog",
        "explore",
        "features",
        "issues",
        "login",
        "marketplace",
        "notifications",
        "orgs",
        "pricing",
        "pulls",
        "search",
        "settings",
        "topics",
    }
)
README_NAMES = ("README.md", "Readme.md", "readme.md", "README", "README.rst")


@dataclass(frozen=True)
class RepoReadme:
    url: str
    readme_url: str
    content: str
    name: str


def parse_repo(raw: str) -> Optional[tuple[str, str, str]]:
    """Return ``(host, owner, repo)`` for a public GitHub/GitLab URL, else None."""
    text = (raw or "").strip()
    if not text:
        return None
    host = owner = repo = ""
    if text.startswith("git@"):
        match = re.match(r"git@([^:]+):([^/]+)/([^/]+?)(?:\.git)?/?$", text)
        if not match:
            return None
        host, owner, repo = match.group(1).lower(), match.group(2), match.group(3)
    else:
        if "://" not in text:
            text = "https://" + text
        parsed = urlparse(text)
        host = (parsed.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        parts = [p for p in (parsed.path or "").split("/") if p]
        if len(parts) < 2:
            return None
        owner, repo = parts[0], parts[1]
        if repo.endswith(".git"):
            repo = repo[:-4]
    if host not in ALLOWED_HOSTS:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner or ""):
        return None
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", repo or ""):
        return None
    if owner.lower() in BLOCKED_OWNERS:
        return None
    return host, owner, repo


def fetch_readme(raw: str, *, get=None) -> RepoReadme:
    """Download the default-branch README. Public repos only; no tokens."""
    parsed = parse_repo(raw)
    if parsed is None:
        raise ValueError(
            "Need a public GitHub or GitLab repo URL, e.g. https://github.com/you/your-service"
        )
    host, owner, repo = parsed
    getter = get or _get
    if host == "github.com":
        return _github_readme(owner, repo, getter)
    return _gitlab_readme(owner, repo, getter)


def _get(url: str, *, headers: Optional[dict] = None) -> requests.Response:
    merged = {"User-Agent": USER_AGENT}
    if headers:
        merged.update(headers)
    return requests.get(url, headers=merged, timeout=TIMEOUT, allow_redirects=True)


def _github_readme(owner: str, repo: str, getter) -> RepoReadme:
    page = f"https://github.com/{owner}/{repo}"
    api = f"https://api.github.com/repos/{owner}/{repo}/readme"
    response = getter(api, headers={"Accept": "application/vnd.github.raw"})
    if getattr(response, "status_code", 0) == 200:
        text = (response.text or "").strip()
        if text:
            return RepoReadme(
                url=page,
                readme_url=f"{page}#readme",
                content=text[:MAX_README_CHARS],
                name="README",
            )
    for name in README_NAMES:
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{name}"
        response = getter(raw_url)
        if getattr(response, "status_code", 0) == 200:
            text = (response.text or "").strip()
            if text:
                return RepoReadme(
                    url=page,
                    readme_url=raw_url,
                    content=text[:MAX_README_CHARS],
                    name=name,
                )
    raise ValueError(
        f"No public README found at {page}. The repo must be public with a README on the default branch."
    )


def _gitlab_readme(owner: str, repo: str, getter) -> RepoReadme:
    page = f"https://gitlab.com/{owner}/{repo}"
    project = quote(f"{owner}/{repo}", safe="")
    for name in README_NAMES:
        api = (
            f"https://gitlab.com/api/v4/projects/{project}/repository/files/"
            f"{quote(name, safe='')}/raw?ref=HEAD"
        )
        response = getter(api)
        if getattr(response, "status_code", 0) == 200:
            text = (response.text or "").strip()
            if text:
                return RepoReadme(
                    url=page,
                    readme_url=f"{page}/-/blob/HEAD/{name}",
                    content=text[:MAX_README_CHARS],
                    name=name,
                )
    raise ValueError(
        f"No public README found at {page}. The repo must be public with a README on the default branch."
    )
