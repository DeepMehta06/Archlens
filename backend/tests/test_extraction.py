"""Extraction and ingestion tests: provenance is rebuilt and verified in code, never trusted."""
from sqlalchemy import select

from app.enums import (
    ApprovalStatus,
    EvidenceStatus,
    JobStatus,
    SourceStatus,
    SourceType,
    StatedBy,
    VerificationStatus,
)
from app.models import EvidenceLink, LedgerItem, Project, Question, SourceChunk
from app.schemas import ExtractionOutput
from app.services.jobs import create_job
from app.services.source_ingestion import create_text_source, process_source
from tests.fakes import FakeEmbedder, FakeLLM, UnavailableEmbedder

CHAT = """12/03/2026, 14:06 - Rahul: Bhai hume ek app chahiye jisme patients appointment book kar sake
12/03/2026, 14:07 - Riya: Payment kaise lena hai?
12/03/2026, 14:08 - Rahul: UPI se lena hai
12/03/2026, 14:09 - Rahul: COD shayad baad me dekhte hain
12/03/2026, 14:10 - Riya: Refund policy kya hogi?
12/03/2026, 14:11 - Rahul: Pata nahi abhi, baad me batata hoon
"""


async def make_project(session, me="Riya"):
    project = Project(name="Clinic", my_name=me)
    session.add(project)
    await session.flush()
    return project


async def run_ingestion(session_factory, llm, embedder, project_id, text=CHAT):
    async with session_factory() as session:
        project = await session.get(Project, project_id)
        source = await create_text_source(session, project, text, label="Clinic chat")
        job = await create_job(session, project.id, source.id, "ingest")
        await session.commit()
        source_id, job_id = source.id, job.id
    await process_source(session_factory, llm, embedder, source_id, job_id)
    return source_id, job_id


async def chunk_id_of(session_factory, source_id):
    async with session_factory() as session:
        return (await session.execute(select(SourceChunk.id).where(SourceChunk.source_id == source_id))).scalars().first()


def payload(chunk_id):
    return {
        "items": [
            {
                "item_type": "requirement",
                "title": "UPI payments",
                "description": "Customers can pay using UPI.",
                "evidence_status": "explicit",
                "risk_level": "low",
                "evidence": [{"chunk_id": chunk_id, "units": [3], "phrase": "UPI se lena hai"}],
            },
            {
                "item_type": "requirement",
                "title": "Cash on delivery",
                "description": "Customers may pay cash on delivery.",
                "evidence_status": "explicit",
                "risk_level": "medium",
                "evidence": [{"chunk_id": chunk_id, "units": [4]}],
            },
            {
                "item_type": "requirement",
                "title": "Refund policy",
                "description": "A refund policy is needed.",
                "evidence_status": "tentative",
                "risk_level": "high",
                "evidence": [{"chunk_id": chunk_id, "units": [5, 6]}],
            },
        ],
        "questions": [
            {"item_index": 2, "question": "What is the refund window?", "reason": "No policy was stated.", "priority": "high"},
        ],
    }


async def ingest_with_llm(session, session_factory, embedder=None, mutate=None):
    project = await make_project(session)
    await session.commit()
    llm = FakeLLM()
    embedder = embedder or UnavailableEmbedder()

    class Lazy(FakeLLM):
        pass

    # Chunk ids are only known after chunking, so the first call builds the payload lazily.
    original = llm.chat_json

    async def chat_json(messages, model_cls, **kwargs):
        chunk_id = messages[1]["content"].split("[CHUNK ")[1].split("]")[0]
        data = payload(chunk_id)
        if mutate:
            mutate(data, chunk_id)
        llm.queue_json(data)
        return await original(messages, model_cls, **kwargs)

    llm.chat_json = chat_json
    source_id, job_id = await run_ingestion(session_factory, llm, embedder, project.id)
    return project, llm, source_id, job_id


async def test_ingestion_creates_verified_evidence_linked_items_and_questions(session, session_factory):
    project, llm, source_id, job_id = await ingest_with_llm(session, session_factory)

    async with session_factory() as s:
        job = await s.get(__import__("app.models", fromlist=["Job"]).Job, job_id)
        items = {i.title: i for i in (await s.execute(select(LedgerItem))).scalars()}
        questions = (await s.execute(select(Question))).scalars().all()

    assert job.status == JobStatus.COMPLETED and job.progress == 100
    assert job.result_json["items_created"] == 3
    assert job.result_json["retrieval_mode"] == "bm25_only"
    upi = items["UPI payments"]
    assert upi.display_id == "REQ-001"
    assert upi.approval_status == ApprovalStatus.NEEDS_REVIEW
    assert upi.evidence_status == EvidenceStatus.EXPLICIT
    assert upi.stated_by == StatedBy.CLIENT
    link = upi.evidence_links[0]
    assert link.quote == "UPI se lena hai"
    assert link.verification_status == VerificationStatus.VERIFIED
    assert link.speaker == "Rahul" and link.speaker_role == StatedBy.CLIENT
    assert link.highlight == "UPI se lena hai"
    assert len(questions) == 1 and questions[0].ledger_item_id == items["Refund policy"].id


async def test_a_client_reply_inside_the_evidence_makes_the_item_client_stated(session, session_factory):
    project, llm, source_id, job_id = await ingest_with_llm(session, session_factory)

    async with session_factory() as s:
        refund = (await s.execute(select(LedgerItem).where(LedgerItem.title == "Refund policy"))).scalars().one()

    link = refund.evidence_links[0]
    assert link.unit_numbers == [5, 6]
    assert link.speaker == "Rahul" and link.speaker_role == StatedBy.CLIENT
    assert refund.stated_by == StatedBy.CLIENT


async def test_hedged_statement_cannot_stay_explicit(session, session_factory):
    project, llm, source_id, job_id = await ingest_with_llm(session, session_factory)

    async with session_factory() as s:
        cod = (await s.execute(select(LedgerItem).where(LedgerItem.title == "Cash on delivery"))).scalars().one()

    assert cod.evidence_status == EvidenceStatus.TENTATIVE
    note = cod.evidence_links[0].verification_note
    assert "shayad" in note and "lowered" in note


async def test_invented_chunk_ids_and_unit_numbers_are_dropped_and_reported(session, session_factory):
    def mutate(data, chunk_id):
        data["items"].append(
            {
                "item_type": "requirement",
                "title": "Loyalty points",
                "description": "Invented.",
                "evidence_status": "explicit",
                "risk_level": "low",
                "evidence": [{"chunk_id": "chk_doesnotexist", "units": [1]}],
            }
        )
        data["items"].append(
            {
                "item_type": "requirement",
                "title": "Dark mode",
                "description": "Invented unit.",
                "evidence_status": "explicit",
                "risk_level": "low",
                "evidence": [{"chunk_id": chunk_id, "units": [99]}],
            }
        )

    project, llm, source_id, job_id = await ingest_with_llm(session, session_factory, mutate=mutate)

    async with session_factory() as s:
        titles = {i.title for i in (await s.execute(select(LedgerItem))).scalars()}
        job = await s.get(__import__("app.models", fromlist=["Job"]).Job, job_id)

    assert titles == {"UPI payments", "Cash on delivery", "Refund policy"}
    dropped = {d["title"] for d in job.result_json["dropped_items"]}
    assert dropped == {"Loyalty points", "Dark mode"}


async def test_duplicate_items_merge_and_keep_every_evidence_link(session, session_factory):
    def mutate(data, chunk_id):
        data["items"].append(
            {
                "item_type": "requirement",
                "title": "UPI payment",
                "description": "Pay by UPI.",
                "evidence_status": "explicit",
                "risk_level": "low",
                "evidence": [{"chunk_id": chunk_id, "units": [2]}],
            }
        )

    project, llm, source_id, job_id = await ingest_with_llm(session, session_factory, mutate=mutate)

    async with session_factory() as s:
        upis = (await s.execute(select(LedgerItem).where(LedgerItem.title.like("UPI%")))).scalars().all()
        links = (await s.execute(select(EvidenceLink).where(EvidenceLink.ledger_item_id == upis[0].id))).scalars().all()

    assert len(upis) == 1
    assert {tuple(l.unit_numbers) for l in links} == {(3,), (2,)}


async def test_model_cannot_pre_approve_items(session, session_factory):
    project, llm, source_id, job_id = await ingest_with_llm(session, session_factory)

    async with session_factory() as s:
        statuses = {i.approval_status for i in (await s.execute(select(LedgerItem))).scalars()}

    assert statuses == {ApprovalStatus.NEEDS_REVIEW}


async def test_dense_embeddings_are_stored_when_the_embedder_is_available(session, session_factory):
    project, llm, source_id, job_id = await ingest_with_llm(session, session_factory, embedder=FakeEmbedder())

    async with session_factory() as s:
        chunks = (await s.execute(select(SourceChunk))).scalars().all()
        job = await s.get(__import__("app.models", fromlist=["Job"]).Job, job_id)

    assert chunks and all(c.embedding_json for c in chunks)
    assert job.result_json["retrieval_mode"] == "hybrid"


async def test_empty_source_fails_the_job_with_a_readable_message(session, session_factory):
    project = await make_project(session)
    await session.commit()

    source_id, job_id = await run_ingestion(session_factory, FakeLLM(), UnavailableEmbedder(), project.id, text="   ")

    async with session_factory() as s:
        from app.models import Job, Source

        job = await s.get(Job, job_id)
        source = await s.get(Source, source_id)

    assert job.status == JobStatus.FAILED
    assert "no readable text" in job.error_message
    assert source.status == SourceStatus.FAILED


async def test_whatsapp_source_records_participants_and_asks_who_you_are(session, session_factory):
    project = Project(name="Clinic")
    session.add(project)
    await session.flush()

    source = await create_text_source(session, project, CHAT)

    assert source.source_type == SourceType.WHATSAPP
    assert source.metadata_json["participants"] == ["Rahul", "Riya"]
    assert source.metadata_json["needs_me"] is True
    assert source.metadata_json["message_count"] == 6
