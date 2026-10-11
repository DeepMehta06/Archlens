"""Turn uploaded PDFs, images and audio into text that the normal pipeline can chunk and cite.

Images and audio are transcribed by the local Gemma model (audio travels in Ollama's ``images`` field).
A transcript is model output, so evidence rebuilt from it is labelled as a transcript quote and the
original file is kept on disk. Text PDFs use pypdf; pages with no text layer fall back to Gemma vision
on a rendered page image. Audio is cut into short segments because the model accepts only short clips.
"""
import io
import wave
from pathlib import Path
from typing import Any

import structlog

from app.enums import EvidenceKind, SourceType

logger = structlog.get_logger()

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
AUDIO_EXTENSIONS = {".wav"}
PDF_EXTENSIONS = {".pdf"}
SEGMENT_SECONDS = 25
MAX_AUDIO_SECONDS = 600
MAX_PDF_PAGES = 30
MAX_VISION_PAGES = 10
MIN_TEXT_CHARS_PER_PAGE = 40

IMAGE_PROMPT = (
    "Transcribe all readable text in this image exactly as written, one line per line of text. "
    "If it is a chat screenshot, keep each message on its own line as 'Sender: message'. "
    "Do not translate, summarise or add anything. If the image contains no readable text, reply with "
    "'DESCRIPTION: ' followed by one or two factual sentences about what it shows."
)
AUDIO_PROMPT = (
    "Transcribe this audio exactly as spoken, in the original language (Hindi or English words may be mixed; "
    "write Hindi in Roman script). Output only the transcript. If there is no speech, reply with '[no speech]'."
)


class MediaError(ValueError):
    pass


def source_type_for(extension: str) -> SourceType | None:
    if extension in IMAGE_EXTENSIONS:
        return SourceType.IMAGE
    if extension in AUDIO_EXTENSIONS:
        return SourceType.AUDIO
    if extension in PDF_EXTENSIONS:
        return SourceType.PDF
    return None


def evidence_kind_for(source_type: SourceType) -> EvidenceKind:
    if source_type in (SourceType.IMAGE, SourceType.AUDIO):
        return EvidenceKind.TRANSCRIPT_QUOTE
    return EvidenceKind.TEXT_QUOTE


async def transcribe_image(llm: Any, data: bytes) -> str:
    result = await llm.chat(
        [{"role": "user", "content": IMAGE_PROMPT}],
        media=[data],
        temperature=0.0,
        think=False,
        num_predict=2048,
        stage="transcribe_image",
    )
    return result.content.strip()


def split_wav(data: bytes, segment_seconds: int = SEGMENT_SECONDS) -> list[bytes]:
    try:
        with wave.open(io.BytesIO(data)) as reader:
            params = reader.getparams()
            frames_per_segment = params.framerate * segment_seconds
            if params.nframes / params.framerate > MAX_AUDIO_SECONDS:
                raise MediaError(f"Audio is longer than {MAX_AUDIO_SECONDS // 60} minutes.")
            segments: list[bytes] = []
            while True:
                frames = reader.readframes(frames_per_segment)
                if not frames:
                    break
                buffer = io.BytesIO()
                with wave.open(buffer, "wb") as writer:
                    writer.setparams(params)
                    writer.writeframes(frames)
                segments.append(buffer.getvalue())
            return segments
    except wave.Error as exc:
        raise MediaError(f"Could not read the WAV file: {exc}") from exc


async def transcribe_audio(llm: Any, data: bytes) -> str:
    parts: list[str] = []
    for segment in split_wav(data):
        result = await llm.chat(
            [{"role": "user", "content": AUDIO_PROMPT}],
            media=[segment],
            temperature=0.0,
            think=False,
            num_predict=1024,
            stage="transcribe_audio",
        )
        text = result.content.strip()
        if text and text.casefold() != "[no speech]":
            parts.append(text)
    return "\n".join(parts)


def pdf_text_pages(data: bytes) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise MediaError("PDF support needs the 'pypdf' package (pip install pypdf).") from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise MediaError("The PDF is password protected.")
        return [(page.extract_text() or "").strip() for page in reader.pages[:MAX_PDF_PAGES]]
    except MediaError:
        raise
    except Exception as exc:
        raise MediaError(f"Could not read the PDF: {exc}") from exc


def render_pdf_page(data: bytes, index: int) -> bytes:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise MediaError("Scanned PDFs need the 'pypdfium2' package (pip install pypdfium2).") from exc
    document = pdfium.PdfDocument(data)
    try:
        image = document[index].render(scale=2).to_pil()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    finally:
        document.close()


async def transcribe_pdf(llm: Any, data: bytes) -> tuple[str, dict[str, Any]]:
    pages = pdf_text_pages(data)
    vision_pages = 0
    out: list[str] = []
    for index, text in enumerate(pages):
        if len(text) < MIN_TEXT_CHARS_PER_PAGE and vision_pages < MAX_VISION_PAGES:
            vision_pages += 1
            text = await transcribe_image(llm, render_pdf_page(data, index))
        if text:
            out.append(text)
    return "\n\n".join(out), {"pages": len(pages), "vision_pages": vision_pages}


async def media_to_text(llm: Any, source_type: SourceType, path: Path) -> tuple[str, dict[str, Any]]:
    data = path.read_bytes()
    if source_type == SourceType.IMAGE:
        text, extra = await transcribe_image(llm, data), {}
    elif source_type == SourceType.AUDIO:
        text, extra = await transcribe_audio(llm, data), {}
    elif source_type == SourceType.PDF:
        text, extra = await transcribe_pdf(llm, data)
    else:
        raise MediaError("Unsupported media type.")
    if not text.strip():
        raise MediaError("No readable text or speech was found in the file.")
    return text, extra
