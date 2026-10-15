"""Read-only async client for the GitHub REST API: fetch a repo's file tree and blob contents.

Scoped to one fine-grained PAT with Contents:Read-only on every repo the user owns -- no git
binary, no disk checkout, no write call anywhere in this client. Single-user: one token for
the account running ArchLens, not a per-user OAuth flow.
"""
import asyncio
import base64
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.config import Settings, get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

GITHUB_API = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"

MAX_FILES = 500
MAX_FILE_BYTES = 200_000
MAX_CONCURRENT_BLOB_FETCHES = 8

TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".java", ".kt", ".go", ".rb", ".php", ".c", ".h", ".cpp", ".hpp", ".cc",
    ".cs", ".rs", ".swift", ".scala", ".m", ".mm",
    ".md", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".html", ".css", ".scss", ".sql", ".sh", ".ps1",
}
SKIP_DIR_PARTS = {
    "node_modules", "vendor", "dist", "build", ".git", "__pycache__", "venv", ".venv",
    "target", ".next", ".nuxt", "coverage", ".pytest_cache", "site-packages",
}
SKIP_FILENAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Cargo.lock",
    "Gemfile.lock", "composer.lock",
}


class GitHubError(Exception):
    status_code = 502


class GitHubUnavailable(GitHubError):
    status_code = 503


class GitHubNotConfigured(GitHubError):
    status_code = 501


class GitHubNotFound(GitHubError):
    status_code = 404


@dataclass
class CodeFile:
    path: str
    text: str


def parse_repo(repo: str) -> tuple[str, str]:
    value = repo.strip()
    for prefix in ("https://github.com/", "http://github.com/", "git@github.com:", "github.com/"):
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    value = value[:-4] if value.endswith(".git") else value
    value = value.strip("/")
    parts = value.split("/")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise GitHubError(f"Could not parse a GitHub owner/repo from '{repo}'.")
    return parts[0], parts[1]


def is_wanted_file(path: str, size: int) -> bool:
    if size > MAX_FILE_BYTES:
        return False
    parts = path.split("/")
    if any(p in SKIP_DIR_PARTS for p in parts[:-1]):
        return False
    filename = parts[-1]
    if filename in SKIP_FILENAMES:
        return False
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in TEXT_EXTENSIONS


class GitHubClient:
    def __init__(self, settings: Optional[Settings] = None, http: Optional[httpx.AsyncClient] = None):
        self._settings = settings or get_settings()
        self._http = http

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=60.0)
        return self._http

    def _headers(self) -> dict[str, str]:
        if not self._settings.GITHUB_READ_TOKEN:
            raise GitHubNotConfigured("GITHUB_READ_TOKEN must be set to connect a repository.")
        return {
            "Authorization": f"Bearer {self._settings.GITHUB_READ_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()

    async def _get(self, path: str, **params: Any) -> Any:
        client = self._client()
        try:
            resp = await client.get(f"{GITHUB_API}{path}", headers=self._headers(), params=params)
        except httpx.HTTPError as exc:
            raise GitHubUnavailable(f"Could not reach GitHub: {exc}") from exc
        if resp.status_code == 404:
            raise GitHubNotFound(
                f"GitHub returned 404 for {path} -- check the repo name and that the token can read it."
            )
        if resp.status_code >= 400:
            raise GitHubError(f"GitHub rejected the request ({resp.status_code}): {resp.text[:300]}")
        return resp.json()

    async def default_branch(self, owner: str, repo: str) -> str:
        data = await self._get(f"/repos/{owner}/{repo}")
        return data["default_branch"]

    async def fetch_files(self, owner: str, repo: str, ref: Optional[str] = None) -> list[CodeFile]:
        branch = ref or await self.default_branch(owner, repo)
        tree = await self._get(f"/repos/{owner}/{repo}/git/trees/{branch}", recursive="1")
        if tree.get("truncated"):
            logger.warning("github_tree_truncated", owner=owner, repo=repo)
        wanted = [
            entry
            for entry in tree.get("tree", [])
            if entry.get("type") == "blob" and is_wanted_file(entry["path"], entry.get("size", 0))
        ][:MAX_FILES]

        client = self._client()
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_BLOB_FETCHES)

        async def fetch_one(entry: dict[str, Any]) -> Optional[CodeFile]:
            async with semaphore:
                try:
                    resp = await client.get(
                        f"{GITHUB_API}/repos/{owner}/{repo}/git/blobs/{entry['sha']}", headers=self._headers()
                    )
                except httpx.HTTPError as exc:
                    raise GitHubUnavailable(f"Could not reach GitHub fetching {entry['path']}: {exc}") from exc
                if resp.status_code >= 400:
                    return None
                blob = resp.json()
                if blob.get("encoding") != "base64":
                    return None
                try:
                    content = base64.b64decode(blob["content"]).decode("utf-8")
                except (UnicodeDecodeError, ValueError):
                    return None
                return CodeFile(path=entry["path"], text=content)

        results = await asyncio.gather(*(fetch_one(entry) for entry in wanted))
        return [f for f in results if f is not None]
