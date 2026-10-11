"""Live evaluation harness for ArchLens.

Runs the real services against a local Ollama server (gemma4:e4b and, if installed, embeddinggemma)
on an in-memory database, so nothing touches the development data. Five suites:

  extraction   planted-fact recall, hedge handling, quote verification, hallucination traps, gap questions
  router       intent accuracy on labelled messages (English and Hinglish)
  retrieval    recall@k and MRR for BM25, dense and hybrid on paraphrased and Hinglish queries
  compare      change classification against a baseline built from the clinic conversation
  invariants   properties that must always hold (never auto-approved, quotes found in source)

Datasets live in evals/datasets. Results are written to evals/results/latest.json.
Usage: python -m evals.run_evals [suite ...] [--repeat N]
"""
import argparse
import asyncio
import json
import re
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select

from app.config import get_settings
from app.database import init_db, make_engine, make_session_factory
from app.enums import ApprovalStatus
from app.models import EvidenceLink, LedgerItem, Project, Question, SourceChunk
from app.services import lexical_search
from app.services.change_detection import compare_request
from app.services.chat_orchestrator import route
from app.services.embeddings import EmbeddingService
from app.services.hybrid_retrieval import Retriever
from app.services.jobs import create_job
from app.services.ollama_client import OllamaClient
from app.services.snapshots import create_snapshot
from app.services.source_ingestion import build_chunk_drafts, create_text_source, process_source, store_chunks

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "datasets"
RESULTS = ROOT / "results"
SUITES = ("extraction", "router", "retrieval", "compare", "invariants")
RETRIEVAL_CHUNK_CHARS = 300


def stats(values: list[Optional[int]]) -> dict[str, Any]:
    n = len(values)
    return {
        "recall@1": round(sum(1 for v in values if v == 1) / n, 3),
        "recall@3": round(sum(1 for v in values if v and v <= 3) / n, 3),
        "mrr": round(sum(1 / v for v in values if v) / n, 3),
        "n": n,
    }



def load(name: str) -> Any:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def contains(text: str, keywords: list[str], whole_word: bool = False) -> bool:
    lowered = text.casefold()
    for keyword in keywords:
        key = keyword.casefold()
        if whole_word:
            if not re.search(rf"(?<!\w){re.escape(key)}(?!\w)", lowered):
                return False
        elif key not in lowered:
            return False
    return True


def matches(text: str, groups: list[list[str]], whole_word: bool = False) -> bool:
    return any(contains(text, group, whole_word) for group in groups)


class Env:
    def __init__(self) -> None:
        self.llm = OllamaClient()
        self.embedder = EmbeddingService(self.llm)
        self.retriever = Retriever(self.embedder)

    async def fresh_db(self):
        engine = make_engine("sqlite+aiosqlite://", in_memory=True)
        await init_db(engine)
        return engine, make_session_factory(engine)

    async def close(self) -> None:
        await self.llm.aclose()


async def ingest(env: Env, factory, conv: dict[str, Any]) -> tuple[str, dict[str, Any], float]:
    text = (DATA / conv["file"]).read_text(encoding="utf-8")
    async with factory() as session:
        project = Project(name=f"eval-{conv['id']}", my_name=conv["me"])
        session.add(project)
        await session.flush()
        source = await create_text_source(session, project, text, label=conv["id"], filename=conv["file"])
        job = await create_job(session, project.id, source.id, "ingest")
        await session.commit()
        project_id, source_id, job_id = project.id, source.id, job.id
    started = time.perf_counter()
    await process_source(factory, env.llm, env.embedder, source_id, job_id)
    elapsed = time.perf_counter() - started
    async with factory() as session:
        from app.models import Job

        job = await session.get(Job, job_id)
        return project_id, {"status": job.status.value, "error": job.error_message, **(job.result_json or {})}, elapsed


async def extraction_metrics(factory, project_id: str, conv: dict[str, Any]) -> dict[str, Any]:
    async with factory() as session:
        items = list((await session.execute(select(LedgerItem).where(LedgerItem.project_id == project_id))).scalars())
        questions = list((await session.execute(select(Question).where(Question.project_id == project_id))).scalars())
        evidence = list(
            (
                await session.execute(
                    select(EvidenceLink).where(EvidenceLink.ledger_item_id.in_([i.id for i in items]))
                )
            ).scalars()
        )
    body = {i.id: f"{i.title} {i.description}" for i in items}
    by_id = {i.id: i for i in items}

    facts = []
    for fact in conv["facts"]:
        hits = [i for i in items if matches(body[i.id], fact["match"])]
        record: dict[str, Any] = {"id": fact["id"], "found": bool(hits), "items": [i.display_id for i in hits]}
        if fact["hedged"]:
            record["hedged_expected"] = True
            record["hedge_respected"] = bool(hits) and all(i.evidence_status.value != "explicit" for i in hits)
        facts.append(record)

    gaps = []
    for gap in conv["gap_questions"]:
        asked = [q for q in questions if matches(f"{q.question} {q.reason}", gap["match"])]
        as_item = [i for i in items if matches(body[i.id], gap["match"])]
        gaps.append({"id": gap["id"], "asked": bool(asked), "also_an_item": bool(as_item)})

    forbidden = []
    for trap in conv["forbidden"]:
        whole = trap.get("whole_word", False)
        unless = trap.get("unless", [])
        hits = [
            i
            for i in items
            if matches(i.title if trap.get("scope") == "title" else body[i.id], trap["match"], whole)
            and not (unless and matches(i.title, unless))
        ]
        forbidden.append({"id": trap["id"], "triggered": bool(hits), "items": [i.display_id for i in hits]})

    verified = sum(e.verification_status.value == "verified" for e in evidence)
    found = [f for f in facts if f["found"]]
    hedged = [f for f in facts if f.get("hedged_expected")]
    return {
        "items": len(items),
        "questions": len(questions),
        "facts": facts,
        "recall": len(found) / len(facts),
        "hedged_total": len(hedged),
        "hedged_respected": sum(bool(f.get("hedge_respected")) for f in hedged),
        "gaps": gaps,
        "gap_recall": sum(g["asked"] for g in gaps) / len(gaps) if gaps else None,
        "traps_triggered": sum(t["triggered"] for t in forbidden),
        "traps": forbidden,
        "evidence_total": len(evidence),
        "evidence_verified": verified,
        "all_needs_review": all(i.approval_status == ApprovalStatus.NEEDS_REVIEW for i in items),
        "item_titles": [f"{i.display_id} [{i.evidence_status.value}] {i.title}" for i in items],
        "question_texts": [q.question for q in questions],
        "_ids": list(by_id),
    }


async def run_extraction(env: Env, repeat: int) -> dict[str, Any]:
    manifest = load("manifest.json")["conversations"]
    out: dict[str, Any] = {"runs": []}
    kept: dict[str, Any] = {}
    for run in range(repeat):
        per_conv = {}
        for conv in manifest:
            engine, factory = await env.fresh_db()
            try:
                project_id, job, elapsed = await ingest(env, factory, conv)
                metrics = await extraction_metrics(factory, project_id, conv)
                metrics.pop("_ids")
                metrics["job"] = job
                metrics["seconds"] = round(elapsed, 1)
                per_conv[conv["id"]] = metrics
                if run == 0 and conv["id"] == "clinic":
                    kept["clinic_items"] = await _approved_snapshot_inputs(factory, project_id)
            finally:
                await engine.dispose()
        out["runs"].append(per_conv)
    out["summary"] = summarise_extraction(out["runs"])
    out["summary_dev"] = summarise_extraction(out["runs"], "dev")
    out["summary_heldout"] = summarise_extraction(out["runs"], "heldout")
    return out


async def _approved_snapshot_inputs(factory, project_id: str) -> list[str]:
    async with factory() as session:
        rows = (await session.execute(select(LedgerItem.title).where(LedgerItem.project_id == project_id))).scalars()
        return list(rows)


def summarise_extraction(runs: list[dict[str, Any]], split: Optional[str] = None) -> dict[str, Any]:
    heldout = {c["id"] for c in load("manifest.json")["conversations"] if c.get("heldout")}
    keep = (lambda cid: True) if split is None else (lambda cid: (cid in heldout) == (split == "heldout"))
    runs = [{cid: m for cid, m in run.items() if keep(cid)} for run in runs]
    rows = [m for run in runs for m in run.values()]
    total_facts = sum(len(m["facts"]) for m in rows)
    found = sum(sum(f["found"] for f in m["facts"]) for m in rows)
    hedged_total = sum(m["hedged_total"] for m in rows)
    hedged_ok = sum(m["hedged_respected"] for m in rows)
    gaps = [g for m in rows for g in m["gaps"]]
    ev_total = sum(m["evidence_total"] for m in rows)
    ev_ok = sum(m["evidence_verified"] for m in rows)
    per_fact: dict[str, list[bool]] = defaultdict(list)
    for run in runs:
        for cid, m in run.items():
            for f in m["facts"]:
                per_fact[f"{cid}/{f['id']}"].append(f["found"])
    return {
        "fact_recall": round(found / total_facts, 3),
        "facts_found": f"{found}/{total_facts}",
        "hedge_respected": f"{hedged_ok}/{hedged_total}",
        "gap_questions_asked": f"{sum(g['asked'] for g in gaps)}/{len(gaps)}",
        "gap_also_extracted_as_item": sum(g["also_an_item"] for g in gaps),
        "traps_triggered": sum(m["traps_triggered"] for m in rows),
        "evidence_verified": f"{ev_ok}/{ev_total}",
        "all_items_needs_review": all(m["all_needs_review"] for m in rows),
        "missed_facts": sorted(k for k, v in per_fact.items() if not all(v)),
        "mean_seconds_per_conversation": round(statistics.mean(m["seconds"] for m in rows), 1),
        "failed_jobs": sum(m["job"]["status"] != "completed" for m in rows),
    }


async def run_router(env: Env, repeat: int) -> dict[str, Any]:
    cases = load("router.json")
    results = []
    latencies = []
    for case in cases:
        for _ in range(repeat):
            started = time.perf_counter()
            routed = await route(env.llm, case["message"])
            latencies.append(time.perf_counter() - started)
            results.append({**case, "got": routed.intent, "ok": routed.intent == case["expected"]})
    by_intent: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        by_intent[r["expected"]].append(r["ok"])
    return {
        "accuracy": f"{sum(r['ok'] for r in results)}/{len(results)}",
        "per_intent": {k: f"{sum(v)}/{len(v)}" for k, v in by_intent.items()},
        "wrong": [r for r in results if not r["ok"]],
        "off_topic_false_positives": sum(r["got"] == "off_topic" and r["expected"] != "off_topic" for r in results),
        "median_seconds": round(statistics.median(latencies), 2),
    }


async def run_retrieval(env: Env) -> dict[str, Any]:
    if not await env.embedder.available():
        return {"skipped": "embeddinggemma is not available, so only BM25 would be measured"}
    queries = load("retrieval.json")
    manifest = {c["id"]: c for c in load("manifest.json")["conversations"]}
    engine, factory = await env.fresh_db()
    try:
        async with factory() as session:
            project = Project(name="eval-retrieval")
            session.add(project)
            await session.flush()
            for conv in manifest.values():
                text = (DATA / conv["file"]).read_text(encoding="utf-8")
                source = await create_text_source(session, project, text, label=conv["id"], me=conv["me"])
                drafts = build_chunk_drafts(source, RETRIEVAL_CHUNK_CHARS)
                chunks = await store_chunks(session, source, drafts)
                await lexical_search.index_chunks(session, chunks)
                vectors = await env.embedder.embed_documents([c.text for c in chunks])
                for chunk, vector in zip(chunks, vectors):
                    chunk.embedding_json = vector
            await session.commit()
            project_id = project.id
            total_chunks = len((await session.execute(select(SourceChunk.id))).all())

        modes = ("bm25", "dense", "hybrid")
        ranks: dict[str, list[Optional[int]]] = {m: [] for m in modes}
        by_split: dict[str, dict[str, list[Optional[int]]]] = defaultdict(lambda: {m: [] for m in modes})
        by_kind: dict[str, dict[str, list[Optional[int]]]] = defaultdict(lambda: {m: [] for m in modes})
        details = []
        async with factory() as session:
            for q in queries:
                found = await env.retriever.search_chunks(session, project_id, q["query"], top_k=30)
                hits = found.hits
                needle = q["expect"].casefold()
                relevant = [h for h in hits if needle in h.text.casefold()]
                orderings = {
                    "hybrid": [h for h in hits],
                    "bm25": sorted((h for h in hits if h.bm25_rank), key=lambda h: h.bm25_rank),
                    "dense": sorted((h for h in hits if h.dense_rank), key=lambda h: h.dense_rank),
                }
                row = {"query": q["query"], "kind": q["kind"], "expect": q["expect"]}
                for mode, ordered in orderings.items():
                    rank = next((n for n, h in enumerate(ordered, start=1) if needle in h.text.casefold()), None)
                    ranks[mode].append(rank)
                    by_kind[q["kind"]][mode].append(rank)
                    by_split[q.get("split", "dev")][mode].append(rank)
                    row[mode] = rank
                row["relevant_found"] = bool(relevant)
                details.append(row)

        sweep: dict[str, Any] = {}
        async with factory() as session:
            for weight in (1.0, 1.5, 2.0, 3.0):
                tuned = Retriever(env.embedder, settings=get_settings().model_copy(update={"RRF_DENSE_WEIGHT": weight}))
                per_split: dict[str, list[Optional[int]]] = defaultdict(list)
                for q in queries:
                    found = await tuned.search_chunks(session, project_id, q["query"], top_k=30)
                    needle = q["expect"].casefold()
                    per_split[q.get("split", "dev")].append(
                        next((n for n, h in enumerate(found.hits, start=1) if needle in h.text.casefold()), None)
                    )
                sweep[f"dense_weight_{weight}"] = {k: stats(v) for k, v in per_split.items()}
    finally:
        await engine.dispose()

    return {
        "chunks_indexed": total_chunks,
        "chunk_chars": RETRIEVAL_CHUNK_CHARS,
        "fusion_sweep": sweep,
        "overall": {m: stats(v) for m, v in ranks.items()},
        "by_split": {k: {m: stats(v) for m, v in modes_.items()} for k, modes_ in by_split.items()},
        "by_query_kind": {k: {m: stats(v) for m, v in modes_.items()} for k, modes_ in by_kind.items()},
        "misses": [d for d in details if d["hybrid"] is None or d["hybrid"] > 3],
    }


async def run_compare(env: Env) -> dict[str, Any]:
    cases = load("compare.json")
    conv = next(c for c in load("manifest.json")["conversations"] if c["id"] == "clinic")
    engine, factory = await env.fresh_db()
    try:
        project_id, _, _ = await ingest(env, factory, conv)
        async with factory() as session:
            items = list((await session.execute(select(LedgerItem).where(LedgerItem.project_id == project_id))).scalars())
            for item in items:
                item.approval_status = ApprovalStatus.APPROVED
            await session.flush()
            snapshot = await create_snapshot(session, project_id, "eval baseline")
            project = await session.get(Project, project_id)
            await session.commit()
            snapshot_items = len(items)
            rows = []
            for case in cases:
                started = time.perf_counter()
                report = await compare_request(
                    session,
                    llm=env.llm,
                    retriever=env.retriever,
                    embedder=env.embedder,
                    project=project,
                    snapshot=snapshot,
                    incoming_text=case["text"],
                )
                await session.commit()
                results = report.results_json["results"]
                classes = [r["classification"] for r in results]
                rows.append(
                    {
                        **case,
                        "got": classes,
                        "primary_ok": bool(classes) and classes[0] == case["expected"],
                        "any_ok": case["expected"] in classes,
                        "seconds": round(time.perf_counter() - started, 1),
                        "related": [r["related_display_ids"] for r in results],
                    }
                )
    finally:
        await engine.dispose()
    confusion = Counter((r["expected"], r["got"][0] if r["got"] else "none") for r in rows)
    return {
        "baseline_items": snapshot_items,
        "primary_accuracy": f"{sum(r['primary_ok'] for r in rows)}/{len(rows)}",
        "any_accuracy": f"{sum(r['any_ok'] for r in rows)}/{len(rows)}",
        "confusion": {f"{a} -> {b}": n for (a, b), n in sorted(confusion.items())},
        "cases": rows,
    }


async def run_invariants(env: Env) -> dict[str, Any]:
    conv = next(c for c in load("manifest.json")["conversations"] if c["id"] == "gym")
    engine, factory = await env.fresh_db()
    try:
        project_id, _, _ = await ingest(env, factory, conv)
        async with factory() as session:
            items = list((await session.execute(select(LedgerItem).where(LedgerItem.project_id == project_id))).scalars())
            links = list(
                (
                    await session.execute(
                        select(EvidenceLink, SourceChunk)
                        .join(SourceChunk, EvidenceLink.chunk_id == SourceChunk.id)
                        .where(EvidenceLink.ledger_item_id.in_([i.id for i in items]))
                    )
                ).all()
            )
    finally:
        await engine.dispose()
    verified = [(e, c) for e, c in links if e.verification_status.value == "verified"]
    def squash(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip().casefold()
    quote_in_source = sum(1 for e, c in verified if e.quote and squash(e.quote) in squash(c.text))
    return {
        "items": len(items),
        "never_auto_approved": all(i.approval_status == ApprovalStatus.NEEDS_REVIEW for i in items),
        "every_item_has_evidence": all(any(e.ledger_item_id == i.id for e, _ in links) for i in items),
        "verified_quotes": len(verified),
        "verified_quotes_found_verbatim_in_source": quote_in_source,
        "devanagari_source_present_in_chunks": any("हिंदी" in c.text for _, c in links),
    }


async def main(suites: list[str], repeat: int) -> dict[str, Any]:
    env = Env()
    health = await env.llm.health()
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": env.llm.model,
        "embed_model": env.llm.embed_model,
        "ollama_health": {k: health[k] for k in ("reachable", "model_installed", "embed_model_installed") if k in health},
        "repeat": repeat,
    }
    try:
        for suite in suites:
            started = time.perf_counter()
            try:
                if suite == "extraction":
                    report[suite] = await run_extraction(env, repeat)
                elif suite == "router":
                    report[suite] = await run_router(env, repeat)
                elif suite == "retrieval":
                    report[suite] = await run_retrieval(env)
                elif suite == "compare":
                    report[suite] = await run_compare(env)
                elif suite == "invariants":
                    report[suite] = await run_invariants(env)
            except Exception as exc:
                report[suite] = {"error": f"{type(exc).__name__}: {exc}"}
            report.setdefault("suite_seconds", {})[suite] = round(time.perf_counter() - started, 1)
            RESULTS.mkdir(exist_ok=True)
            (RESULTS / "latest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[{suite}] done in {report['suite_seconds'][suite]}s", flush=True)
    finally:
        await env.close()
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "latest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("suites", nargs="*", choices=[*SUITES, []], default=[])
    parser.add_argument("--repeat", type=int, default=2)
    args = parser.parse_args()
    result = asyncio.run(main(args.suites or list(SUITES), args.repeat))
    summary = {k: (v.get("summary", v) if isinstance(v, dict) else v) for k, v in result.items()}
    print(json.dumps(summary, indent=2, ensure_ascii=False)[:6000])
