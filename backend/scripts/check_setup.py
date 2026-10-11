"""
Preflight check for a local ArchLens setup.

Verifies SQLite FTS5, the Ollama server, both configured models, schema-constrained
output with thinking disabled, and generation speed. Exits non-zero only when the core
path (Ollama plus the chat model) is unusable; a missing embedding model only degrades
retrieval to BM25.

Usage (from backend/): python -m scripts.check_setup
"""
import json
import sqlite3
import sys

import httpx

from app.config import get_settings

OK, FAIL, WARN = "[ OK ]", "[FAIL]", "[WARN]"

SMOKE_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"title": {"type": "string"}, "status": {"type": "string", "enum": ["explicit", "tentative"]}},
                "required": ["title", "status"],
            },
        }
    },
    "required": ["items"],
}


def report(status: str, message: str) -> None:
    print(f"{status} {message}")


def check_fts5() -> bool:
    try:
        sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE t USING fts5(a)")
    except sqlite3.Error:
        report(FAIL, "SQLite FTS5 is not available in this Python build")
        return False
    report(OK, f"SQLite {sqlite3.sqlite_version} with FTS5")
    return True


def installed(name: str, names: list[str]) -> bool:
    return name in names if ":" in name else any(n.split(":")[0] == name for n in names)


def check_ollama(settings) -> bool:
    base = settings.OLLAMA_BASE_URL.rstrip("/")
    try:
        tags = httpx.get(f"{base}/api/tags", timeout=5.0)
        tags.raise_for_status()
    except Exception as exc:
        report(FAIL, f"Ollama not reachable at {base}: {exc}")
        return False
    report(OK, f"Ollama reachable at {base}")
    names = [m.get("name", "") for m in tags.json().get("models", [])]

    if not installed(settings.OLLAMA_EMBED_MODEL, names):
        report(WARN, f"Embedding model '{settings.OLLAMA_EMBED_MODEL}' not pulled: retrieval will run BM25-only. Run: ollama pull {settings.OLLAMA_EMBED_MODEL}")
    else:
        report(OK, f"Embedding model '{settings.OLLAMA_EMBED_MODEL}' is installed")

    if not installed(settings.OLLAMA_MODEL, names):
        report(FAIL, f"Model '{settings.OLLAMA_MODEL}' not pulled. Run: ollama pull {settings.OLLAMA_MODEL}")
        return False
    report(OK, f"Model '{settings.OLLAMA_MODEL}' is installed")

    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [{"role": "user", "content": "Extract two requirements from: 'We need UPI payments. Maybe cash too.'"}],
        "stream": False,
        "think": settings.OLLAMA_THINK,
        "format": SMOKE_SCHEMA,
        "options": {"temperature": 0.1, "num_ctx": settings.OLLAMA_NUM_CTX, "num_predict": 512},
    }
    try:
        response = httpx.post(f"{base}/api/chat", json=payload, timeout=settings.OLLAMA_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
        parsed = json.loads(data["message"]["content"])
        count = len(parsed["items"])
    except Exception as exc:
        report(FAIL, f"Schema-constrained smoke test failed: {exc}")
        return False
    report(OK, f"Schema-constrained output parsed ({count} items)")

    tokens, ns = data.get("eval_count"), data.get("eval_duration")
    if tokens and ns:
        report(OK, f"Generation speed: {tokens / (ns / 1e9):.1f} tokens/s ({tokens} tokens, load {data.get('load_duration', 0) / 1e9:.1f}s)")
    return True


def main() -> int:
    settings = get_settings()
    print(f"Model: {settings.OLLAMA_MODEL}  Embeddings: {settings.OLLAMA_EMBED_MODEL}  Data: {settings.data_dir}\n")
    fts_ok = check_fts5()
    model_ok = check_ollama(settings)
    print()
    ready = fts_ok and model_ok
    print("Core path ready." if ready else "Core path NOT ready.")
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
