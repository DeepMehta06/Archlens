"""Test doubles for the local model runtime. No network or Ollama server is needed."""
import json
from typing import Any, Optional

from pydantic import BaseModel

from app.services.embeddings import EmbeddingService, normalize_vectors
from app.services.notion_export import NotionExportResult
from app.services.ollama_client import ChatResult

CONCEPTS = [
    {"pay", "payment", "payments", "upi", "paisa", "paise", "cod", "cash"},
    {"refund", "return", "wapas", "cancel", "cancellation"},
    {"doctor", "doctors", "dr", "physician"},
    {"loyalty", "referral", "rewards", "points", "cashback"},
    {"appointment", "booking", "book", "slot"},
]


def concept_vector(text: str) -> list[float]:
    words = {w.strip(".,!?:;\"'").lower() for w in text.split()}
    vector = [float(len(words & concept)) for concept in CONCEPTS]
    if not any(vector):
        vector = [0.01] * len(CONCEPTS)
    return vector


class FakeEmbedder(EmbeddingService):
    """Maps words to hand-built concept dimensions: tests the dense channel's plumbing,
    not real semantic quality."""

    def __init__(self) -> None:
        pass

    async def available(self) -> bool:
        return True

    async def embed_documents(self, texts: list[str]) -> Optional[list[list[float]]]:
        return normalize_vectors([concept_vector(t) for t in texts]).tolist()

    async def embed_query(self, query: str) -> Optional[list[float]]:
        return normalize_vectors([concept_vector(query)])[0].tolist()


class UnavailableEmbedder(EmbeddingService):
    def __init__(self) -> None:
        pass

    async def available(self) -> bool:
        return False

    async def embed_documents(self, texts: list[str]) -> Optional[list[list[float]]]:
        return None

    async def embed_query(self, query: str) -> Optional[list[float]]:
        return None


class FakeLLM:
    """Replays queued structured responses and records every call for assertions."""

    model = "fake-gemma"
    embed_model = "fake-embed"

    def __init__(self) -> None:
        self.json_queue: list[BaseModel | dict[str, Any]] = []
        self.text_queue: list[str] = []
        self.calls: list[dict[str, Any]] = []
        self.extraction_factory = None

    def queue_json(self, payload: BaseModel | dict[str, Any]) -> None:
        self.json_queue.append(payload)

    def queue_text(self, text: str) -> None:
        self.text_queue.append(text)

    async def health(self) -> dict[str, Any]:
        return {
            "reachable": True,
            "model": self.model,
            "model_installed": True,
            "embed_model": self.embed_model,
            "embed_model_installed": True,
            "error": None,
        }

    async def chat_json(self, messages, model_cls, **kwargs):
        self.calls.append({"kind": "json", "messages": messages, "model": model_cls.__name__, **kwargs})
        if model_cls.__name__ == "ExtractionOutput" and self.extraction_factory is not None:
            chunk_id = messages[1]["content"].split("[CHUNK ")[1].split("]")[0]
            return model_cls.model_validate(self.extraction_factory(chunk_id))
        if not self.json_queue:
            raise AssertionError("FakeLLM has no queued JSON response")
        payload = self.json_queue.pop(0)
        if isinstance(payload, BaseModel):
            return model_cls.model_validate(payload.model_dump())
        return model_cls.model_validate(payload)

    async def chat(self, messages, **kwargs) -> ChatResult:
        self.calls.append({"kind": "chat", "messages": messages, **kwargs})
        text = self.text_queue.pop(0) if self.text_queue else ""
        return ChatResult(content=text)

    async def stream_chat(self, messages, **kwargs):
        self.calls.append({"kind": "stream", "messages": messages, **kwargs})
        text = self.text_queue.pop(0) if self.text_queue else ""
        for word in text.split(" "):
            yield word + " "

    async def aclose(self) -> None:
        return None


class FakeNotionClient:
    """Records every page it was asked to create instead of calling the real Notion API."""

    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []

    async def create_page(self, title: str, blocks: list[dict[str, Any]]) -> NotionExportResult:
        self.created.append({"title": title, "blocks": blocks})
        return NotionExportResult(page_id="fake_page_id", url="https://notion.so/fake_page_id")


def as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
