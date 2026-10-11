import io
import wave

import numpy as np

from PIL import Image
from sqlalchemy import select

from app.enums import EvidenceKind
from app.models import EvidenceLink, Source
from app.services.media_ingestion import MediaError, split_wav
from tests.test_api import env, make_project  # noqa: F401

TRANSCRIPT = "Dr. Mehra: UPI se lena hai, advance payment chahiye booking ke time"


def one_item(chunk_id):
    return {
        "items": [
            {
                "item_type": "requirement",
                "title": "UPI advance payment",
                "description": "Patients pay in advance by UPI.",
                "evidence_status": "explicit",
                "risk_level": "medium",
                "evidence": [{"chunk_id": chunk_id, "units": [1]}],
            }
        ],
        "questions": [],
    }


def wav_bytes(seconds, rate=8000):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(b"\x00\x00" * rate * seconds)
    return buffer.getvalue()


def text_pdf(text):
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


async def upload(client, project_id, name, data, mime):
    r = await client.post(f"/api/projects/{project_id}/sources/upload", files={"file": (name, data, mime)})
    assert r.status_code == 201, r.text
    return r.json()


async def evidence(session_factory):
    async with session_factory() as s:
        return list((await s.execute(select(EvidenceLink))).scalars())


async def test_image_is_transcribed_then_cited_as_a_transcript_quote(env, session_factory):
    client, llm, _ = env
    llm.extraction_factory = one_item
    llm.queue_text(TRANSCRIPT)
    project_id = await make_project(client)
    image = io.BytesIO()
    Image.new("RGB", (40, 20), "white").save(image, format="PNG")

    created = await upload(client, project_id, "chat.png", image.getvalue(), "image/png")

    job = (await client.get(f"/api/jobs/{created['job']['id']}")).json()
    assert job["status"] == "completed", job
    assert created["source"]["source_type"] == "image"
    assert llm.calls[0]["kind"] == "chat" and llm.calls[0]["media"][0].startswith(b"\x89PNG")
    links = await evidence(session_factory)
    assert links[0].evidence_kind == EvidenceKind.TRANSCRIPT_QUOTE
    assert "transcript" in links[0].verification_note
    assert links[0].quote == TRANSCRIPT
    async with session_factory() as s:
        source = (await s.execute(select(Source))).scalar_one()
    assert source.raw_text == TRANSCRIPT and source.file_path


async def test_long_audio_is_cut_into_segments_and_joined(env, session_factory):
    client, llm, _ = env
    llm.extraction_factory = one_item
    llm.queue_text("Pehla hissa.")
    llm.queue_text("Doosra hissa.")
    project_id = await make_project(client)

    created = await upload(client, project_id, "note.wav", wav_bytes(40), "audio/wav")

    assert (await client.get(f"/api/jobs/{created['job']['id']}")).json()["status"] == "completed"
    assert sum(1 for c in llm.calls if c["kind"] == "chat") == 2
    async with session_factory() as s:
        assert (await s.execute(select(Source))).scalar_one().raw_text == "Pehla hissa.\nDoosra hissa."


def test_split_wav_cuts_in_silence_not_mid_word():
    rate = 8000
    loud = (np.ones(rate * 40) * 5000).astype(np.int16)
    loud[int(rate * 22.0) : int(rate * 22.3)] = 0
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(loud.tobytes())

    first, second = split_wav(buffer.getvalue())

    with wave.open(io.BytesIO(first)) as w:
        cut_seconds = w.getnframes() / rate
    assert 22.0 <= cut_seconds <= 22.3
    with wave.open(io.BytesIO(second)) as w:
        assert abs(w.getnframes() / rate - (40 - cut_seconds)) < 0.01


def test_split_wav_segments_and_rejects_garbage():
    segments = split_wav(wav_bytes(60))
    assert 3 <= len(segments) <= 4
    for segment in segments:
        with wave.open(io.BytesIO(segment)) as w:
            assert w.getnframes() / w.getframerate() <= 25.01
    try:
        split_wav(b"not a wav")
    except MediaError:
        return
    raise AssertionError("expected MediaError")


async def test_text_pdf_uses_the_text_layer_without_calling_the_model(env, session_factory):
    client, llm, _ = env
    llm.extraction_factory = one_item
    project_id = await make_project(client)

    created = await upload(
        client, project_id, "brief.pdf", text_pdf("Client wants UPI payments with advance booking and nothing else"), "application/pdf"
    )

    assert (await client.get(f"/api/jobs/{created['job']['id']}")).json()["status"] == "completed"
    assert not [c for c in llm.calls if c["kind"] == "chat"]
    assert (await evidence(session_factory))[0].evidence_kind == EvidenceKind.TEXT_QUOTE


async def test_scanned_pdf_falls_back_to_vision_per_page(env, session_factory):
    client, llm, _ = env
    llm.extraction_factory = one_item
    llm.queue_text(TRANSCRIPT)
    project_id = await make_project(client)
    scan = io.BytesIO()
    Image.new("RGB", (200, 200), "white").save(scan, format="PDF")

    created = await upload(client, project_id, "scan.pdf", scan.getvalue(), "application/pdf")

    assert (await client.get(f"/api/jobs/{created['job']['id']}")).json()["status"] == "completed"
    assert sum(1 for c in llm.calls if c["kind"] == "chat") == 1


async def test_media_with_no_readable_content_fails_with_a_clear_message(env):
    client, llm, _ = env
    llm.queue_text("[no speech]")
    project_id = await make_project(client)

    created = await upload(client, project_id, "silence.wav", wav_bytes(3), "audio/wav")

    job = (await client.get(f"/api/jobs/{created['job']['id']}")).json()
    assert job["status"] == "failed" and "No readable text" in job["error_message"]


async def test_media_call_unloads_models_and_retries_once_on_a_runner_failure():
    from app.services.media_ingestion import transcribe_image
    from app.services.ollama_client import OllamaBadResponse
    from tests.fakes import FakeLLM

    class Flaky(FakeLLM):
        unloaded = 0
        failures = 1

        async def chat(self, messages, **kwargs):
            if self.failures:
                self.failures -= 1
                raise OllamaBadResponse("Ollama returned HTTP 500: out of memory")
            return await super().chat(messages, **kwargs)

        async def unload_all(self):
            self.unloaded += 1

    llm = Flaky()
    llm.queue_text("Sender: hello")
    assert await transcribe_image(llm, b"img") == "Sender: hello"
    assert llm.unloaded == 1

    llm = Flaky()
    llm.failures = 2
    try:
        await transcribe_image(llm, b"img")
    except OllamaBadResponse:
        assert llm.unloaded == 1
        return
    raise AssertionError("second failure should propagate")
