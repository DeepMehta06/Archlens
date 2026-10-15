"""GitHub repo parsing, file filtering, chunking and ingestion -- never produces ledger items."""
from app.enums import SourceType
from app.models import LedgerItem, Project, Source
from app.services.code_ingestion import chunk_file, create_github_source, process_github_source
from app.services.github_client import CodeFile, GitHubError, is_wanted_file, parse_repo
from sqlalchemy import select
from tests.fakes import FakeEmbedder, FakeGitHubClient, UnavailableEmbedder


def test_parse_repo_accepts_owner_slash_repo_and_full_urls():
    assert parse_repo("octocat/hello-world") == ("octocat", "hello-world")
    assert parse_repo("https://github.com/octocat/hello-world") == ("octocat", "hello-world")
    assert parse_repo("https://github.com/octocat/hello-world.git") == ("octocat", "hello-world")
    assert parse_repo("git@github.com:octocat/hello-world.git") == ("octocat", "hello-world")


def test_parse_repo_rejects_garbage():
    try:
        parse_repo("not-a-repo")
        assert False, "expected GitHubError"
    except GitHubError:
        pass


def test_file_filter_skips_vendor_dirs_lockfiles_and_oversized_files():
    assert is_wanted_file("app/payments.py", 1000) is True
    assert is_wanted_file("node_modules/left-pad/index.js", 1000) is False
    assert is_wanted_file("package-lock.json", 1000) is False
    assert is_wanted_file("app/huge.py", 10_000_000) is False
    assert is_wanted_file("app/image.png", 1000) is False


def test_chunk_file_tracks_line_ranges_and_includes_a_path_header():
    file = CodeFile(path="app/payments.py", text="\n".join(f"line {i}" for i in range(1, 201)))

    chunks = chunk_file(file, lines_per_chunk=80)

    assert len(chunks) == 3
    first_text, first_loc = chunks[0]
    assert first_loc == {"file_path": "app/payments.py", "start_line": 1, "end_line": 80}
    assert "app/payments.py" in first_text and "line 1" in first_text
    assert chunks[2][1] == {"file_path": "app/payments.py", "start_line": 161, "end_line": 200}


async def test_github_ingestion_indexes_code_but_never_creates_ledger_items(session, session_factory):
    project = Project(name="Clinic")
    session.add(project)
    await session.flush()
    source = await create_github_source(session, project, "octocat/hello-world", None)
    from app.services.jobs import create_job

    job = await create_job(session, project.id, source.id, "github_ingest")
    await session.commit()

    github = FakeGitHubClient(
        files=[
            CodeFile(path="app/refund.py", text="def refund_policy():\n    return '7 days'\n"),
            CodeFile(path="app/payments.py", text="def charge(upi_id):\n    pass\n"),
        ]
    )

    await process_github_source(session_factory, FakeEmbedder(), source.id, job.id, github)

    async with session_factory() as verify:
        refreshed_source = await verify.get(Source, source.id)
        assert refreshed_source.source_type == SourceType.GITHUB_REPO
        assert refreshed_source.status.value == "processed"
        items = (await verify.execute(select(LedgerItem).where(LedgerItem.project_id == project.id))).scalars().all()
        assert items == []


async def test_github_ingestion_without_embeddings_still_completes_bm25_only(session, session_factory):
    project = Project(name="Clinic")
    session.add(project)
    await session.flush()
    source = await create_github_source(session, project, "octocat/hello-world", "main")
    from app.services.jobs import create_job

    job = await create_job(session, project.id, source.id, "github_ingest")
    await session.commit()

    await process_github_source(session_factory, UnavailableEmbedder(), source.id, job.id, FakeGitHubClient())

    async with session_factory() as verify:
        refreshed = await verify.get(Source, source.id)
        assert refreshed.status.value == "processed"
        from app.models import Job

        job_row = await verify.get(Job, job.id)
        assert job_row.result_json["retrieval_mode"] == "bm25_only"


async def test_github_ingestion_reports_no_files_honestly(session, session_factory):
    project = Project(name="Clinic")
    session.add(project)
    await session.flush()
    source = await create_github_source(session, project, "octocat/empty-repo", None)
    from app.services.jobs import create_job

    job = await create_job(session, project.id, source.id, "github_ingest")
    await session.commit()

    await process_github_source(session_factory, FakeEmbedder(), source.id, job.id, FakeGitHubClient(files=[]))

    async with session_factory() as verify:
        refreshed = await verify.get(Source, source.id)
        assert refreshed.status.value == "failed"
        assert "No readable source files" in refreshed.error_message
