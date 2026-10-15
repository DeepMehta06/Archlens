"""HTTP-level acceptance tests with a fake model and an in-memory database."""
import json
from pathlib import Path

import httpx
import pytest

from app.config import Settings, get_settings
from app.database import get_db
from app.deps import get_embedder, get_github_client, get_llm, get_notion_client, get_session_factory_dep
from app.main import app
from app.services.github_client import CodeFile
from app.services.notion_export import NotionClient
from tests.fakes import FakeEmbedder, FakeGitHubClient, FakeLLM, FakeNotionClient, UnavailableEmbedder

DEMO_CHAT = (Path(__file__).resolve().parent.parent / "app" / "demo" / "pune_clinic_chat.txt").read_text(
    encoding="utf-8"
)


def extraction(chunk_id: str) -> dict:
    def item(kind, title, desc, status, risk, units):
        return {
            "item_type": kind,
            "title": title,
            "description": desc,
            "evidence_status": status,
            "risk_level": risk,
            "evidence": [{"chunk_id": chunk_id, "units": units}],
        }

    return {
        "items": [
            item("requirement", "Doctor approves bookings", "Every booking needs doctor approval.", "explicit", "medium", [4]),
            item("requirement", "UPI advance payment", "Patients pay in advance by UPI.", "explicit", "medium", [6]),
            item("requirement", "Cash at clinic", "Patients may pay cash at the clinic.", "explicit", "low", [7]),
            item("requirement", "Refund policy", "A cancellation refund rule is needed.", "unknown", "high", [8, 9]),
            item("constraint", "Eight week timeline", "Delivery within 8 weeks.", "explicit", "medium", [10]),
            item("requirement", "WhatsApp reminders", "Reminders go out on WhatsApp, not SMS.", "explicit", "low", [12]),
        ],
        "questions": [
            {"item_index": 3, "question": "What is the refund rule for cancellations?", "reason": "The client has not decided.", "priority": "high"},
            {"item_index": 2, "question": "Is cash at the clinic confirmed?", "reason": "The client said maybe.", "priority": "medium"},
        ],
    }


@pytest.fixture
async def env(session_factory):
    llm = FakeLLM()
    llm.extraction_factory = extraction
    holder = {"embedder": UnavailableEmbedder()}

    async def override_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_session_factory_dep] = lambda: session_factory
    app.dependency_overrides[get_llm] = lambda: llm
    app.dependency_overrides[get_embedder] = lambda: holder["embedder"]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, llm, holder
    app.dependency_overrides.clear()


async def make_project(client, name="Clinic", my_name="Riya"):
    r = await client.post("/api/projects", json={"name": name, "my_name": my_name})
    assert r.status_code == 201
    return r.json()["id"]


async def import_chat(client, project_id, text=DEMO_CHAT):
    r = await client.post(f"/api/projects/{project_id}/sources", json={"text": text, "label": "Clinic chat"})
    assert r.status_code == 201, r.text
    return r.json()


async def ready_project(client):
    project_id = await make_project(client)
    created = await import_chat(client, project_id)
    job = (await client.get(f"/api/jobs/{created['job']['id']}")).json()
    assert job["status"] == "completed", job
    return project_id, created["source"]["id"], job


def parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.strip().split("\n\n"):
        data = [line[6:] for line in block.split("\n") if line.startswith("data: ")]
        if data:
            events.append(json.loads(data[0]))
    return events


async def test_health_reports_models_retrieval_mode_and_honest_privacy_text(env):
    client, llm, holder = env

    body = (await client.get("/api/health")).json()

    assert body["status"] == "ok"
    assert body["model_installed"] is True
    assert body["retrieval_mode"] == "bm25_only"
    assert "no cloud AI provider" in body["privacy"]
    assert "network" in body["privacy"]

    holder["embedder"] = FakeEmbedder()
    assert (await client.get("/api/health")).json()["retrieval_mode"] == "hybrid"


async def test_text_ingestion_creates_ledger_items_with_verified_evidence(env):
    client, llm, _ = env
    project_id, source_id, job = await ready_project(client)

    items = (await client.get(f"/api/projects/{project_id}/ledger")).json()

    assert job["result_json"]["items_created"] == 6
    assert len(items) == 6
    assert {i["approval_status"] for i in items} == {"needs_review"}
    cash = next(i for i in items if i["title"] == "Cash at clinic")
    assert cash["evidence_status"] == "tentative"
    assert cash["stated_by"] == "client"
    detail = (await client.get(f"/api/ledger-items/{cash['id']}")).json()
    evidence = detail["evidence"][0]
    assert evidence["quote"].startswith("Cash at clinic bhi allow kar sakte hain shayad")
    assert evidence["verification_status"] == "verified"
    assert "shayad" in evidence["verification_note"]
    assert evidence["source_label"] == "Clinic chat"
    assert evidence["chunk"]["units_json"][6]["n"] == 7
    assert [q["question"] for q in detail["questions"]] == ["Is cash at the clinic confirmed?"]


async def test_approval_snapshot_and_projects_are_isolated(env):
    client, llm, _ = env
    project_id, _, _ = await ready_project(client)
    items = (await client.get(f"/api/projects/{project_id}/ledger")).json()
    upi = next(i for i in items if i["title"] == "UPI advance payment")
    refund = next(i for i in items if i["title"] == "Refund policy")

    empty = await client.post(f"/api/projects/{project_id}/snapshots", json={})
    assert empty.status_code == 409

    patched = await client.patch(f"/api/ledger-items/{upi['id']}", json={"approval_status": "approved"})
    assert patched.json()["approval_status"] == "approved"
    await client.patch(f"/api/ledger-items/{refund['id']}", json={"approval_status": "rejected"})
    snap = (await client.post(f"/api/projects/{project_id}/snapshots", json={"label": "Kickoff"})).json()

    assert snap["version"] == 1 and snap["label"] == "Kickoff"
    assert [i["display_id"] for i in snap["snapshot_json"]["items"]] == [upi["display_id"]]
    second = (await client.post(f"/api/projects/{project_id}/snapshots", json={})).json()
    assert second["version"] == 2

    other = await make_project(client, name="Other")
    cross = await client.post(
        f"/api/projects/{other}/compare", json={"snapshot_id": snap["id"], "incoming_text": "add loyalty points"}
    )
    assert cross.status_code == 404


async def test_compare_validates_ids_and_files_new_requests_for_review(env):
    client, llm, _ = env
    project_id, _, _ = await ready_project(client)
    items = (await client.get(f"/api/projects/{project_id}/ledger")).json()
    upi = next(i for i in items if i["title"] == "UPI advance payment")
    await client.patch(f"/api/ledger-items/{upi['id']}", json={"approval_status": "approved"})
    snap = (await client.post(f"/api/projects/{project_id}/snapshots", json={})).json()
    llm.queue_json(
        {
            "changes": [
                {"incoming_claim": "Add loyalty points", "classification": "new_requirement", "related_baseline_ids": ["REQ-001"], "units": [1], "explanation": "Not in baseline.", "confidence": "high"},
                {"incoming_claim": "Accept credit cards", "classification": "contradiction", "related_baseline_ids": ["REQ-777"], "units": [1], "explanation": "Conflicts.", "confidence": "high"},
                {"incoming_claim": "UPI is needed", "classification": "already_covered", "related_baseline_ids": [upi["display_id"].lower()], "units": [1], "explanation": "Covered.", "confidence": "medium"},
            ]
        }
    )

    report = (
        await client.post(
            f"/api/projects/{project_id}/compare",
            json={"snapshot_id": snap["id"], "incoming_text": "Patients ko loyalty points chahiye."},
        )
    ).json()

    by_claim = {r["incoming_claim"]: r for r in report["results"]}
    new = by_claim["Add loyalty points"]
    assert new["classification"] == "new_requirement" and new["related_display_ids"] == []
    assert new["candidate_item_id"]
    bogus = by_claim["Accept credit cards"]
    assert bogus["classification"] == "unclear"
    assert "No valid baseline item" in bogus["explanation"]
    covered = by_claim["UPI is needed"]
    assert covered["classification"] == "already_covered"
    assert covered["related_baseline_item_ids"] == [upi["id"]]
    candidate = (await client.get(f"/api/ledger-items/{new['candidate_item_id']}")).json()
    assert candidate["approval_status"] == "needs_review"
    assert candidate["evidence"][0]["quote"] == "Patients ko loyalty points chahiye."
    fetched = (await client.get(f"/api/change-reports/{report['id']}")).json()
    assert len(fetched["results"]) == 3


async def test_draft_message_uses_open_questions_and_rejects_foreign_ids(env):
    client, llm, _ = env
    project_id, _, _ = await ready_project(client)
    llm.queue_text("Hi! Kuch points clear karne the:\n1. Refund rule kya hoga?\nThanks!")

    draft = (await client.post(f"/api/projects/{project_id}/draft-message", json={"language": "hinglish"})).json()

    assert "Refund rule" in draft["text"]
    assert draft["language"] == "hinglish"
    assert len(draft["question_ids"]) == 2
    prompt = llm.calls[-1]["messages"][1]["content"]
    assert prompt.startswith("Language: hinglish") and "refund rule" in prompt.lower()
    other = await make_project(client, name="Other")
    bad = await client.post(f"/api/projects/{other}/draft-message", json={"question_ids": draft["question_ids"]})
    assert bad.status_code == 404


async def test_export_contains_baseline_evidence_questions_and_legend(env):
    client, llm, _ = env
    project_id, _, _ = await ready_project(client)
    items = (await client.get(f"/api/projects/{project_id}/ledger")).json()
    upi = next(i for i in items if i["title"] == "UPI advance payment")
    await client.patch(f"/api/ledger-items/{upi['id']}", json={"approval_status": "approved"})
    await client.post(f"/api/projects/{project_id}/snapshots", json={"label": "Kickoff"})

    response = await client.get(f"/api/projects/{project_id}/export.md")

    md = response.text
    assert response.headers["content-disposition"].startswith("attachment")
    assert "# Scope brief: Clinic" in md
    assert "Kickoff (version 1)" in md
    assert "UPI advance payment" in md and "UPI se lena hai" in md and "[verified]" in md
    assert "What is the refund rule for cancellations?" in md
    assert "## Awaiting review" in md and "Refund policy" in md
    assert "not a legal contract" in md


async def test_notion_export_without_configuration_errors_clearly(env):
    client, _, _ = env
    project_id, _, _ = await ready_project(client)
    # Deliberately blanked regardless of this machine's real .env, so the test is hermetic.
    unconfigured = NotionClient(settings=Settings(NOTION_API_KEY=None, NOTION_PARENT_PAGE_ID=None))
    app.dependency_overrides[get_notion_client] = lambda: unconfigured

    response = await client.post(f"/api/projects/{project_id}/export/notion")

    del app.dependency_overrides[get_notion_client]
    assert response.status_code == 501
    assert "NOTION_API_KEY" in response.json()["detail"]


async def test_notion_export_creates_a_page_titled_after_the_project(env):
    client, _, _ = env
    project_id, _, _ = await ready_project(client)
    items = (await client.get(f"/api/projects/{project_id}/ledger")).json()
    upi = next(i for i in items if i["title"] == "UPI advance payment")
    await client.patch(f"/api/ledger-items/{upi['id']}", json={"approval_status": "approved"})
    await client.post(f"/api/projects/{project_id}/snapshots", json={"label": "Kickoff"})
    fake_notion = FakeNotionClient()
    app.dependency_overrides[get_notion_client] = lambda: fake_notion

    response = await client.post(f"/api/projects/{project_id}/export/notion")

    del app.dependency_overrides[get_notion_client]
    assert response.status_code == 201
    assert response.json() == {"page_id": "fake_page_id", "url": "https://notion.so/fake_page_id"}
    assert len(fake_notion.created) == 1
    assert fake_notion.created[0]["title"] == "Clinic"
    block_texts = [
        b[b["type"]]["rich_text"][0]["text"]["content"]
        for b in fake_notion.created[0]["blocks"]
        if b[b["type"]]["rich_text"]
    ]
    assert any("UPI advance payment" in t for t in block_texts)
    assert any("Kickoff" in t for t in block_texts)


async def test_diagram_endpoint_compiles_spec_and_reports_dropped_references(env):
    client, llm, _ = env
    project_id, _, _ = await ready_project(client)
    llm.queue_json(
        {
            "nodes": [{"id": "app", "label": 'Patient "App"'}, {"id": "api", "label": "API"}],
            "edges": [{"from": "app", "to": "api", "label": "book"}, {"from": "api", "to": "ghost", "label": "x"}],
        }
    )

    r = await client.post(f"/api/projects/{project_id}/diagrams", json={"diagram_type": "architecture"})

    body = r.json()
    assert r.status_code == 201
    assert body["mermaid_source"].startswith("flowchart TD")
    assert "ghost" not in body["mermaid_source"]
    assert any("Dropped 1 reference" in w for w in body["warnings_json"])
    assert len((await client.get(f"/api/projects/{project_id}/diagrams")).json()) == 1


async def test_diagram_with_an_empty_ledger_is_a_clear_conflict(env):
    client, llm, _ = env
    project_id = await make_project(client)

    r = await client.post(f"/api/projects/{project_id}/diagrams", json={"diagram_type": "sequence"})

    assert r.status_code == 409 and "nothing to draw" in r.json()["detail"]


async def test_upload_accepts_text_and_rejects_other_types_and_oversized_files(env, monkeypatch):
    client, llm, _ = env
    project_id = await make_project(client)

    ok = await client.post(
        f"/api/projects/{project_id}/sources/upload", files={"file": ("chat.txt", DEMO_CHAT.encode(), "text/plain")}
    )
    assert ok.status_code == 201 and ok.json()["source"]["source_type"] == "whatsapp"
    assert ok.json()["job"]["status"] in ("queued", "completed")

    docx = await client.post(
        f"/api/projects/{project_id}/sources/upload", files={"file": ("a.docx", b"PK", "application/octet-stream")}
    )
    assert docx.status_code == 415

    monkeypatch.setattr(get_settings(), "MAX_UPLOAD_BYTES", 10)
    big = await client.post(
        f"/api/projects/{project_id}/sources/upload", files={"file": ("big.txt", b"x" * 50, "text/plain")}
    )
    assert big.status_code == 413


async def test_github_source_indexes_code_without_running_extraction(env):
    client, llm, _ = env
    project_id = await make_project(client)
    fake_github = FakeGitHubClient(
        files=[CodeFile(path="app/refund.py", text="def refund_policy():\n    return '7 days'\n")]
    )
    app.dependency_overrides[get_github_client] = lambda: fake_github

    created = await client.post(f"/api/projects/{project_id}/sources/github", json={"repo": "octocat/hello-world"})
    assert created.status_code == 201
    source = created.json()["source"]
    assert source["source_type"] == "github_repo" and source["label"] == "octocat/hello-world"
    job = (await client.get(f"/api/jobs/{created.json()['job']['id']}")).json()
    assert job["status"] == "completed", job
    assert job["result_json"]["files"] == 1

    del app.dependency_overrides[get_github_client]
    assert fake_github.requested == [("octocat", "hello-world", None)]
    assert (await client.get(f"/api/projects/{project_id}/ledger")).json() == []
    assert not [c for c in llm.calls if c["model"] == "ExtractionOutput"]


async def test_github_source_rejects_an_unparsable_repo(env):
    client, _, _ = env
    project_id = await make_project(client)

    bad = await client.post(f"/api/projects/{project_id}/sources/github", json={"repo": "not-a-repo"})

    assert bad.status_code == 502
    assert "owner/repo" in bad.json()["detail"]


async def test_change_prompt_requires_a_connected_repo_first(env):
    client, _, _ = env
    project_id, _, _ = await ready_project(client)
    items = (await client.get(f"/api/projects/{project_id}/ledger")).json()
    refund = next(i for i in items if i["title"] == "Refund policy")

    response = await client.post(f"/api/ledger-items/{refund['id']}/prompt", json={})

    assert response.status_code == 409
    assert "Connect" in response.json()["detail"]


async def test_change_prompt_cites_only_retrieved_files_and_strips_invented_markers(env):
    client, llm, _ = env
    project_id, _, _ = await ready_project(client)
    items = (await client.get(f"/api/projects/{project_id}/ledger")).json()
    refund = next(i for i in items if i["title"] == "Refund policy")

    fake_github = FakeGitHubClient(
        files=[CodeFile(path="app/refund.py", text="# refund policy implementation\ndef calculate():\n    return 7\n")]
    )
    app.dependency_overrides[get_github_client] = lambda: fake_github
    connected = await client.post(f"/api/projects/{project_id}/sources/github", json={"repo": "octocat/hello-world"})
    assert connected.status_code == 201
    job = (await client.get(f"/api/jobs/{connected.json()['job']['id']}")).json()
    assert job["status"] == "completed", job

    llm.queue_text(
        "Goal: implement the refund rule.\n"
        "Evidence: the client said the refund rule is not decided.\n"
        "Affected areas: [F1] looks directly relevant. [F2] does not exist.\n"
        "Suggested approach: update [F1] once the policy is confirmed."
    )
    result = await client.post(f"/api/ledger-items/{refund['id']}/prompt", json={"target": "claude_code"})

    del app.dependency_overrides[get_github_client]
    assert result.status_code == 200
    body = result.json()
    assert body["target"] == "claude_code"
    assert "app/refund.py:1-3" in body["prompt"]
    assert "[F1]" not in body["prompt"] and "[F2]" not in body["prompt"]
    assert body["affected_files"] == [{"file_path": "app/refund.py", "start_line": 1, "end_line": 3}]


async def test_telling_the_app_who_you_are_recomputes_who_stated_each_item(env):
    client, llm, _ = env
    project_id = await make_project(client, my_name=None)
    created = await import_chat(client, project_id)
    source_id = created["source"]["id"]
    assert created["source"]["metadata_json"]["needs_me"] is True
    items = (await client.get(f"/api/projects/{project_id}/ledger")).json()
    assert {i["stated_by"] for i in items} == {"unknown"}

    patched = await client.patch(f"/api/projects/{project_id}/sources/{source_id}", json={"me": "Riya"})

    assert patched.json()["metadata_json"]["needs_me"] is False
    items = (await client.get(f"/api/projects/{project_id}/ledger")).json()
    assert {i["stated_by"] for i in items} == {"client"}


async def test_demo_seed_is_labelled_and_idempotent(env):
    client, llm, _ = env

    first = (await client.post("/api/demo/seed")).json()
    second = (await client.post("/api/demo/seed")).json()

    assert first["created"] is True and second["created"] is False
    assert first["project"]["is_demo"] is True and "demo data" in first["project"]["name"].lower()
    assert first["sources"][0]["label"].startswith("DEMO DATA")
    assert "loyalty points" in first["compare_example"]
    assert second["project"]["id"] == first["project"]["id"]
    ledger = (await client.get(f"/api/projects/{first['project']['id']}/ledger")).json()
    assert len(ledger) == 6


async def test_deleting_a_project_removes_its_data_and_search_index(env, session_factory):
    from sqlalchemy import text

    client, llm, _ = env
    project_id, _, _ = await ready_project(client)

    assert (await client.delete(f"/api/projects/{project_id}")).status_code == 204

    assert (await client.get(f"/api/projects/{project_id}")).status_code == 404
    async with session_factory() as s:
        for table in ("chunk_fts", "item_fts", "ledger_items", "source_chunks", "evidence_links"):
            assert (await s.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar_one() == 0, table


async def test_chat_answer_streams_validates_citations_and_persists(env):
    client, llm, holder = env
    holder["embedder"] = FakeEmbedder()
    project_id, _, _ = await ready_project(client)
    llm.queue_json({"intent": "answer_question", "query": "refund policy"})
    llm.queue_text("Client ne refund ka rule abhi decide nahi kiya [C1] [C9].")

    response = await client.post(f"/api/projects/{project_id}/chat", json={"message": "Refund ke baare me client ne kya kaha?"})

    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    kinds = [e["type"] for e in events]
    assert kinds[0] == "thread" and kinds[-1] == "done"
    assert "token" in kinds and "citations" in kinds
    replace = next(e for e in events if e["type"] == "replace")
    assert "[C9]" not in replace["text"] and "[C1]" in replace["text"]
    citations = next(e for e in events if e["type"] == "citations")
    assert citations["grounded"] is True
    assert [c["marker"] for c in citations["citations"]] == ["C1"]
    assert citations["citations"][0]["kind"] == "chunk" and citations["citations"][0]["source_label"] == "Clinic chat"
    answer_prompt = llm.calls[-1]["messages"][-1]["content"]
    assert answer_prompt.startswith("CONTEXT:") and "refund" in answer_prompt.lower()
    history = (await client.get(f"/api/projects/{project_id}/chat/messages")).json()
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert "[C9]" not in history[1]["content"]
    assert history[1]["citations_json"][0]["marker"] == "C1"


async def test_chat_without_cited_markers_is_flagged_not_grounded(env):
    client, llm, _ = env
    project_id, _, _ = await ready_project(client)
    llm.queue_json({"intent": "answer_question", "query": "refund"})
    llm.queue_text("The refund is probably seven days.")

    events = parse_sse((await client.post(f"/api/projects/{project_id}/chat", json={"message": "refund kitna?"})).text)

    citations = next(e for e in events if e["type"] == "citations")
    assert citations["grounded"] is False and citations["citations"] == []
    assert events[-1]["grounded"] is False


async def test_chat_says_not_found_instead_of_inventing_when_nothing_is_retrieved(env):
    client, llm, _ = env
    project_id, _, _ = await ready_project(client)
    llm.queue_json({"intent": "answer_question", "query": "kubernetes helm charts"})
    llm.queue_json({"give_up": True})

    events = parse_sse((await client.post(f"/api/projects/{project_id}/chat", json={"message": "kubernetes helm charts?"})).text)

    text = "".join(e["text"] for e in events if e["type"] == "token")
    assert "couldn't find anything" in text
    assert not any(c["kind"] for e in events if e["type"] == "citations" for c in e["citations"])
    assert not [c for c in llm.calls if c["kind"] == "stream"]
    reformulate_calls = [c for c in llm.calls if c["kind"] == "json" and c["model"] == "ReformulateOutput"]
    assert len(reformulate_calls) == 1


async def test_chat_reformulates_the_query_once_when_the_first_search_finds_nothing(env):
    client, llm, _ = env
    project_id, _, _ = await ready_project(client)
    llm.queue_json({"intent": "answer_question", "query": "wapsi ki niyam"})
    llm.queue_json({"give_up": False, "query": "refund"})
    llm.queue_text("Client ne refund ka rule abhi decide nahi kiya [C1].")

    events = parse_sse(
        (await client.post(f"/api/projects/{project_id}/chat", json={"message": "wapsi ki niyam kya hai?"})).text
    )

    stages = [e.get("stage") for e in events if e["type"] == "status"]
    assert stages == ["routing", "searching", "reformulating", "searching", "writing"]
    citations = next(e for e in events if e["type"] == "citations")
    assert citations["grounded"] is True
    answer_prompt = llm.calls[-1]["messages"][-1]["content"]
    assert "refund" in answer_prompt.lower()


async def test_chat_cards_for_ledger_questions_draft_and_diagram(env):
    client, llm, _ = env
    project_id, _, _ = await ready_project(client)

    llm.queue_json({"intent": "list_ledger", "query": "payment"})
    cards = [e["card"] for e in parse_sse((await client.post(f"/api/projects/{project_id}/chat", json={"message": "show payment items"})).text) if e["type"] == "card"]
    assert cards[0]["type"] == "ledger_list" and {i["title"] for i in cards[0]["items"]} == {"UPI advance payment"}

    llm.queue_json({"intent": "open_questions"})
    cards = [e["card"] for e in parse_sse((await client.post(f"/api/projects/{project_id}/chat", json={"message": "what is unclear?"})).text) if e["type"] == "card"]
    assert [q["priority"] for q in cards[0]["questions"]] == ["high", "medium"]

    llm.queue_json({"intent": "draft_message", "language": "hinglish"})
    llm.queue_text("Hi, ek doubt tha...")
    cards = [e["card"] for e in parse_sse((await client.post(f"/api/projects/{project_id}/chat", json={"message": "hinglish me client ko likho"})).text) if e["type"] == "card"]
    assert cards[0]["type"] == "draft_message" and cards[0]["language"] == "hinglish" and cards[0]["text"].startswith("Hi")

    llm.queue_json({"intent": "create_diagram", "diagram_type": "sequence"})
    llm.queue_json(
        {
            "participants": [{"id": "p", "label": "Patient"}, {"id": "d", "label": "Doctor"}],
            "messages": [{"from": "p", "to": "d", "action": "book"}],
        }
    )
    cards = [e["card"] for e in parse_sse((await client.post(f"/api/projects/{project_id}/chat", json={"message": "draw the booking flow"})).text) if e["type"] == "card"]
    assert cards[0]["type"] == "diagram" and cards[0]["mermaid_source"].startswith("sequenceDiagram")


async def test_chat_off_topic_and_paste_prompt_make_no_model_answer_call(env):
    client, llm, _ = env
    project_id, _, _ = await ready_project(client)
    llm.queue_json({"intent": "off_topic"})

    events = parse_sse((await client.post(f"/api/projects/{project_id}/chat", json={"message": "write me a poem"})).text)
    assert "only help with this project" in "".join(e["text"] for e in events if e["type"] == "token")

    paste = parse_sse((await client.post(f"/api/projects/{project_id}/chat", json={"message": DEMO_CHAT})).text)
    card = next(e["card"] for e in paste if e["type"] == "card")
    assert card["type"] == "confirm_add_source" and card["looks_like_whatsapp"] is True
    assert not [c for c in llm.calls if c["kind"] == "json" and c["model"] == "RouterOutput"][1:]


async def test_chat_compare_without_a_baseline_explains_what_to_do(env):
    client, llm, _ = env
    project_id, _, _ = await ready_project(client)
    llm.queue_json({"intent": "compare_request", "query": "add loyalty points"})

    events = parse_sse((await client.post(f"/api/projects/{project_id}/chat", json={"message": "is loyalty in scope?"})).text)

    assert "no approved baseline" in "".join(e["text"] for e in events if e["type"] == "token")


async def test_chat_router_failure_falls_back_to_a_grounded_answer_attempt(env):
    client, llm, _ = env
    project_id, _, _ = await ready_project(client)
    from app.services.ollama_client import OllamaBadResponse

    async def broken(messages, model_cls, **kwargs):
        raise OllamaBadResponse("bad json")

    llm.chat_json = broken
    llm.queue_text("Refund abhi decide nahi hua [C1].")

    events = parse_sse((await client.post(f"/api/projects/{project_id}/chat", json={"message": "refund"})).text)

    assert next(e for e in events if e["type"] == "citations")["grounded"] is True


async def test_chat_threads_are_scoped_to_their_project(env):
    client, llm, _ = env
    project_a = await make_project(client, name="A")
    project_b = await make_project(client, name="B")
    llm.queue_json({"intent": "off_topic"})
    events = parse_sse((await client.post(f"/api/projects/{project_a}/chat", json={"message": "hello"})).text)
    thread_id = events[0]["thread_id"]

    wrong = await client.post(f"/api/projects/{project_b}/chat", json={"message": "hi", "thread_id": thread_id})

    assert wrong.status_code == 404
    assert (await client.get(f"/api/projects/{project_b}/chat/messages", params={"thread_id": thread_id})).status_code == 404
    assert (await client.post("/api/projects/prj_missing/chat", json={"message": "hi"})).status_code == 404
