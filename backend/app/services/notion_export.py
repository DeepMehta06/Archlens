"""Export the scope brief to Notion as a new page under a fixed parent, titled after the project.

No model is involved: this re-uses the exact markdown ``export_service.build_markdown`` already
produces and converts it into Notion blocks, so the Notion export and the Markdown export can
never silently drift apart in content. The converter is narrow on purpose -- it only handles the
line shapes ``build_markdown`` actually emits (headings, flat bullets, paragraphs), it is not a
general markdown parser.
"""
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models import Project
from app.services.export_service import build_markdown

NOTION_VERSION = "2022-06-28"
NOTION_BASE = "https://api.notion.com/v1"
MAX_BLOCKS_PER_REQUEST = 100
MAX_RICH_TEXT_CHARS = 2000


class NotionError(Exception):
    status_code = 502


class NotionNotConfigured(NotionError):
    status_code = 501


@dataclass
class NotionExportResult:
    page_id: str
    url: str


def _text(content: str, *, italic: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": "text", "text": {"content": content[:MAX_RICH_TEXT_CHARS]}}
    if italic:
        payload["annotations"] = {"italic": True}
    return payload


def _rich_text(content: str) -> list[dict[str, Any]]:
    italic = content.startswith("_") and content.endswith("_") and len(content) > 1
    return [_text(content[1:-1] if italic else content, italic=italic)]


def markdown_to_blocks(markdown: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for raw_line in markdown.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("### "):
            blocks.append({"type": "heading_3", "heading_3": {"rich_text": _rich_text(line[4:])}})
        elif line.startswith("## "):
            blocks.append({"type": "heading_2", "heading_2": {"rich_text": _rich_text(line[3:])}})
        elif line.startswith("# "):
            blocks.append({"type": "heading_1", "heading_1": {"rich_text": _rich_text(line[2:])}})
        elif line.startswith("- "):
            blocks.append({"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": _rich_text(line[2:])}})
        else:
            blocks.append({"type": "paragraph", "paragraph": {"rich_text": _rich_text(line)}})
    return blocks


class NotionClient:
    def __init__(self, settings: Optional[Settings] = None, http: Optional[httpx.AsyncClient] = None):
        self._settings = settings or get_settings()
        self._http = http

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.NOTION_API_KEY}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()

    async def create_page(self, title: str, blocks: list[dict[str, Any]]) -> NotionExportResult:
        if not self._settings.NOTION_API_KEY or not self._settings.NOTION_PARENT_PAGE_ID:
            raise NotionNotConfigured("NOTION_API_KEY and NOTION_PARENT_PAGE_ID must both be set to export to Notion.")

        client = self._client()
        first, rest = blocks[:MAX_BLOCKS_PER_REQUEST], blocks[MAX_BLOCKS_PER_REQUEST:]
        payload = {
            "parent": {"page_id": self._settings.NOTION_PARENT_PAGE_ID},
            "properties": {"title": {"title": [_text(title[:MAX_RICH_TEXT_CHARS])]}},
            "children": first,
        }
        try:
            resp = await client.post(f"{NOTION_BASE}/pages", headers=self._headers(), json=payload)
        except httpx.HTTPError as exc:
            raise NotionError(f"Could not reach Notion: {exc}") from exc
        if resp.status_code >= 400:
            raise NotionError(f"Notion rejected the export ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        page_id = data["id"]
        url = data.get("url") or f"https://notion.so/{page_id.replace('-', '')}"

        for i in range(0, len(rest), MAX_BLOCKS_PER_REQUEST):
            batch = rest[i : i + MAX_BLOCKS_PER_REQUEST]
            try:
                resp = await client.patch(
                    f"{NOTION_BASE}/blocks/{page_id}/children", headers=self._headers(), json={"children": batch}
                )
            except httpx.HTTPError as exc:
                raise NotionError(f"Could not reach Notion while appending content: {exc}") from exc
            if resp.status_code >= 400:
                raise NotionError(f"Notion rejected appended content ({resp.status_code}): {resp.text[:300]}")

        return NotionExportResult(page_id=page_id, url=url)


async def export_project(session: AsyncSession, project: Project, client: NotionClient) -> NotionExportResult:
    markdown = await build_markdown(session, project)
    blocks = markdown_to_blocks(markdown)
    return await client.create_page(project.name, blocks)
