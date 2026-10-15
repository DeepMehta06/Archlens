"""GitHub repository ingestion: fetch, chunk, index and embed code for retrieval only.

A github_repo source never goes through extraction.py. A codebase is reference material for
answering "what does this requirement touch", not something a client said -- no ledger items
or evidence links are ever produced from it. Chunks live in the same source_chunks table as
every other source, but hybrid_retrieval.py partitions the two domains by source_type so code
never leaks into chat answers or change detection, and conversation text never leaks into a
code-affected-files lookup.
"""
import hashlib
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.enums import JobStatus, SourceStatus, SourceType
from app.logging_config import get_logger
from app.models import Project, Source, SourceChunk
from app.services import lexical_search
from app.services.embeddings import EmbeddingService
from app.services.github_client import CodeFile, GitHubClient, GitHubError, parse_repo
from app.services.jobs import fail_source_and_job, update_job

logger = get_logger(__name__)

LINES_PER_CHUNK = 80


async def create_github_source(
    session: AsyncSession, project: Project, repo: str, ref: Optional[str]
) -> Source:
    owner, name = parse_repo(repo)
    source = Source(
        project_id=project.id,
        source_type=SourceType.GITHUB_REPO,
        label=f"{owner}/{name}",
        metadata_json={"owner": owner, "repo": name, "ref": ref},
        status=SourceStatus.UPLOADED,
    )
    session.add(source)
    await session.flush()
    return source


def chunk_file(file: CodeFile, lines_per_chunk: int = LINES_PER_CHUNK) -> list[tuple[str, dict]]:
    lines = file.text.splitlines()
    chunks: list[tuple[str, dict]] = []
    for start in range(0, len(lines), lines_per_chunk):
        body = "\n".join(lines[start : start + lines_per_chunk])
        if not body.strip():
            continue
        end = min(start + lines_per_chunk, len(lines))
        location = {"file_path": file.path, "start_line": start + 1, "end_line": end}
        text = f"# {file.path} (lines {location['start_line']}-{end})\n{body}"
        chunks.append((text, location))
    return chunks


async def process_github_source(
    session_factory: async_sessionmaker[AsyncSession],
    embedder: EmbeddingService,
    source_id: str,
    job_id: str,
    github: Optional[GitHubClient] = None,
) -> None:
    client = github or GitHubClient()
    try:
        await update_job(session_factory, job_id, status=JobStatus.PROCESSING, stage="fetching", progress=5)
        async with session_factory() as session:
            source = await session.get(Source, source_id)
            if source is None:
                raise ValueError("Source not found.")
            source.status = SourceStatus.PROCESSING
            meta = source.metadata_json or {}
            owner, repo, ref = meta["owner"], meta["repo"], meta.get("ref")
            await session.commit()

        files = await client.fetch_files(owner, repo, ref)
        if not files:
            raise ValueError(
                "No readable source files were found in this repository "
                "(check the branch/ref, or it may contain only file types ArchLens doesn't index)."
            )

        await update_job(session_factory, job_id, stage="indexing", progress=40)
        async with session_factory() as session:
            source = await session.get(Source, source_id)
            rows: list[SourceChunk] = []
            ordinal = 0
            for file in files:
                for text, location in chunk_file(file):
                    rows.append(
                        SourceChunk(
                            project_id=source.project_id,
                            source_id=source.id,
                            ordinal=ordinal,
                            text=text,
                            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                            units_json=[],
                            location_json=location,
                        )
                    )
                    ordinal += 1
            if not rows:
                raise ValueError("Every file in this repository was empty after chunking.")
            session.add_all(rows)
            await session.flush()
            await lexical_search.index_chunks(session, rows)

            await update_job(session_factory, job_id, stage="embedding", progress=70)
            vectors = await embedder.embed_documents([r.text for r in rows])
            retrieval_mode = "hybrid"
            if vectors is None:
                retrieval_mode = "bm25_only"
            else:
                for row, vector in zip(rows, vectors):
                    row.embedding_json = vector

            source.status = SourceStatus.PROCESSED
            source.processed_at = datetime.now(timezone.utc)
            await session.commit()
            chunk_count = len(rows)

        result = {"files": len(files), "chunks": chunk_count, "retrieval_mode": retrieval_mode}
        await update_job(
            session_factory, job_id, status=JobStatus.COMPLETED, stage="complete", progress=100, result=result
        )
    except (GitHubError, ValueError) as exc:
        await fail_source_and_job(session_factory, source_id, job_id, str(exc))
    except Exception:
        logger.exception("github_ingestion_failed", source_id=source_id)
        await fail_source_and_job(
            session_factory, source_id, job_id, "Repository import failed unexpectedly. Check the server logs."
        )
