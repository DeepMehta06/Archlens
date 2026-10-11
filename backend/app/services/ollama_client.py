"""Async client for the local Ollama server: chat, streaming, structured JSON and embeddings.

All model traffic goes to the configured localhost endpoint. Images and audio are attached
through the message ``images`` field, the path Ollama uses for audio-capable models; the
``audio`` field is silently ignored by ``/api/chat``. Private message content is never logged.
"""
import base64
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Optional, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)
T = TypeVar("T", bound=BaseModel)
EMBED_BATCH = 16


class OllamaError(Exception):
    status_code = 502


class OllamaUnavailable(OllamaError):
    status_code = 503


class OllamaModelMissing(OllamaError):
    status_code = 503


class OllamaTimeout(OllamaError):
    status_code = 504


class OllamaBadResponse(OllamaError):
    status_code = 502


@dataclass
class ChatResult:
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    thinking: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    tokens_per_second: Optional[float] = None
    done_reason: Optional[str] = None


def _model_installed(name: str, installed: list[str]) -> bool:
    if ":" in name:
        return name in installed
    return any(n.split(":")[0] == name for n in installed)


class OllamaClient:
    def __init__(self, settings: Optional[Settings] = None, http: Optional[httpx.AsyncClient] = None):
        self._settings = settings or get_settings()
        self._http = http
        self._base = self._settings.OLLAMA_BASE_URL.rstrip("/")

    @property
    def model(self) -> str:
        return self._settings.OLLAMA_MODEL

    @property
    def embed_model(self) -> str:
        return self._settings.OLLAMA_EMBED_MODEL

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self._settings.OLLAMA_TIMEOUT_SECONDS)
        return self._http

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client().post(f"{self._base}{path}", json=payload)
        except httpx.ConnectError as exc:
            raise OllamaUnavailable(
                f"Ollama is not reachable at {self._base}. Start it with `ollama serve`."
            ) from exc
        except httpx.TimeoutException as exc:
            raise OllamaTimeout("The local model timed out; raise OLLAMA_TIMEOUT_SECONDS.") from exc
        self._raise_for_status(response)
        try:
            return response.json()
        except ValueError as exc:
            raise OllamaBadResponse("Ollama returned a response that is not JSON.") from exc

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code == 404:
            raise OllamaModelMissing(f"Model not found: {response.text[:200]}. Pull it with `ollama pull`.")
        if response.status_code >= 400:
            raise OllamaBadResponse(f"Ollama returned HTTP {response.status_code}: {response.text[:200]}")

    async def unload_all(self) -> None:
        for name in (self.model, self.embed_model):
            try:
                await self._post("/api/generate", {"model": name, "keep_alive": 0, "stream": False})
            except OllamaError as exc:
                logger.info("ollama_unload_skipped", model=name, error=str(exc)[:120])

    async def installed_models(self) -> list[str]:
        try:
            response = await self._client().get(f"{self._base}/api/tags", timeout=5.0)
            response.raise_for_status()
        except (httpx.HTTPError, OSError) as exc:
            raise OllamaUnavailable(f"Ollama is not reachable at {self._base}.") from exc
        return [m.get("name", "") for m in response.json().get("models", [])]

    async def health(self) -> dict[str, Any]:
        try:
            installed = await self.installed_models()
        except OllamaError as exc:
            return {
                "reachable": False,
                "model": self.model,
                "model_installed": False,
                "embed_model": self.embed_model,
                "embed_model_installed": False,
                "error": str(exc),
            }
        return {
            "reachable": True,
            "model": self.model,
            "model_installed": _model_installed(self.model, installed),
            "embed_model": self.embed_model,
            "embed_model_installed": _model_installed(self.embed_model, installed),
            "error": None,
        }

    def _payload(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool,
        schema: Optional[dict[str, Any]],
        think: Optional[bool],
        tools: Optional[list[dict[str, Any]]],
        temperature: float,
        num_predict: Optional[int],
        media: Optional[list[bytes]],
    ) -> dict[str, Any]:
        messages = [dict(m) for m in messages]
        if media:
            for message in reversed(messages):
                if message["role"] == "user":
                    message["images"] = [base64.b64encode(b).decode() for b in media]
                    break
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "think": self._settings.OLLAMA_THINK if think is None else think,
            "options": {
                "temperature": temperature,
                "num_ctx": self._settings.OLLAMA_NUM_CTX,
                "num_predict": num_predict or self._settings.OLLAMA_NUM_PREDICT,
            },
        }
        if schema is not None:
            payload["format"] = schema
        if tools:
            payload["tools"] = tools
        return payload

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        schema: Optional[dict[str, Any]] = None,
        think: Optional[bool] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        temperature: float = 0.1,
        num_predict: Optional[int] = None,
        media: Optional[list[bytes]] = None,
        stage: str = "chat",
    ) -> ChatResult:
        started = time.monotonic()
        data = await self._post(
            "/api/chat",
            self._payload(
                messages,
                stream=False,
                schema=schema,
                think=think,
                tools=tools,
                temperature=temperature,
                num_predict=num_predict,
                media=media,
            ),
        )
        message = data.get("message") or {}
        completion = data.get("eval_count")
        eval_ns = data.get("eval_duration") or 0
        result = ChatResult(
            content=message.get("content") or "",
            tool_calls=message.get("tool_calls") or [],
            thinking=message.get("thinking"),
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=completion,
            tokens_per_second=round(completion / (eval_ns / 1e9), 1) if completion and eval_ns else None,
            done_reason=data.get("done_reason"),
        )
        logger.info(
            "ollama_chat",
            stage=stage,
            seconds=round(time.monotonic() - started, 2),
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            tokens_per_second=result.tokens_per_second,
        )
        return result

    async def chat_json(
        self,
        messages: list[dict[str, Any]],
        model_cls: type[T],
        *,
        stage: str = "chat_json",
        **kwargs: Any,
    ) -> T:
        schema = model_cls.model_json_schema()
        conversation = list(messages)
        last_error = ""
        for attempt in range(2):
            result = await self.chat(conversation, schema=schema, stage=stage, **kwargs)
            if result.done_reason == "length":
                raise OllamaBadResponse(
                    "The model output was cut off at the token limit; raise OLLAMA_NUM_PREDICT."
                )
            try:
                return model_cls.model_validate_json(result.content)
            except (ValidationError, ValueError) as exc:
                last_error = str(exc)[:600]
                logger.warning("ollama_json_invalid", stage=stage, attempt=attempt + 1)
                conversation = conversation + [
                    {"role": "assistant", "content": result.content},
                    {
                        "role": "user",
                        "content": "That reply was invalid: "
                        f"{last_error}\nReturn only corrected JSON that matches the schema.",
                    },
                ]
        raise OllamaBadResponse(f"The model did not return valid JSON after one retry: {last_error}")

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        *,
        think: Optional[bool] = None,
        temperature: float = 0.2,
        num_predict: Optional[int] = None,
    ) -> AsyncIterator[str]:
        payload = self._payload(
            messages,
            stream=True,
            schema=None,
            think=think,
            tools=None,
            temperature=temperature,
            num_predict=num_predict,
            media=None,
        )
        try:
            async with self._client().stream("POST", f"{self._base}/api/chat", json=payload) as response:
                if response.status_code >= 400:
                    await response.aread()
                    self._raise_for_status(response)
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except ValueError:
                        continue
                    delta = (chunk.get("message") or {}).get("content")
                    if delta:
                        yield delta
                    if chunk.get("done"):
                        return
        except httpx.ConnectError as exc:
            raise OllamaUnavailable(f"Ollama is not reachable at {self._base}.") from exc
        except httpx.TimeoutException as exc:
            raise OllamaTimeout("The local model timed out while streaming.") from exc

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH):
            batch = texts[start : start + EMBED_BATCH]
            data = await self._post("/api/embed", {"model": self.embed_model, "input": batch})
            embeddings = data.get("embeddings")
            if not isinstance(embeddings, list) or len(embeddings) != len(batch):
                raise OllamaBadResponse("Ollama returned an unexpected embeddings payload.")
            vectors.extend(embeddings)
        return vectors
