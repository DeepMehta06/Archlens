"""Retrieval tests: BM25, dense channel plumbing, RRF fusion, project isolation, fallback."""
from app.enums import SourceStatus, SourceType
from app.models import Project, Source, SourceChunk
from app.services import lexical_search
from app.services.hybrid_retrieval import Retriever
from tests.fakes import FakeEmbedder, UnavailableEmbedder, concept_vector
from app.services.embeddings import normalize_vectors


async def add_chunk(session, project, source, ordinal, text, embed=True):
    chunk = SourceChunk(
        project_id=project.id,
        source_id=source.id,
        ordinal=ordinal,
        text=text,
        content_hash=f"h{ordinal}{project.id}",
        units_json=[{"n": 1, "text": text}],
        embedding_json=normalize_vectors([concept_vector(text)]).tolist()[0] if embed else None,
    )
    session.add(chunk)
    await session.flush()
    await lexical_search.index_chunks(session, [chunk])
    return chunk


async def make_project(session, name):
    project = Project(name=name)
    session.add(project)
    await session.flush()
    source = Source(
        project_id=project.id,
        source_type=SourceType.TEXT,
        label=f"{name} chat",
        status=SourceStatus.PROCESSED,
    )
    session.add(source)
    await session.flush()
    return project, source


async def seed(session):
    project, source = await make_project(session, "Clinic")
    chunks = {
        "upi": await add_chunk(session, project, source, 0, "Rahul: UPI se lena hai payment"),
        "refund": await add_chunk(session, project, source, 1, "Riya: refund policy abhi decide nahi hui"),
        "doctor": await add_chunk(session, project, source, 2, "Rahul: doctors ko approve karna hoga"),
        "hindi": await add_chunk(
            session, project, source, 3, "ग्राहक को ऑर्डर ट्रैक करना है"
        ),
    }
    await session.commit()
    return project, source, chunks


async def test_bm25_exact_term_retrieves_the_chunk_containing_it(session):
    project, _, chunks = await seed(session)

    ranked = await lexical_search.search_chunks(session, project.id, "refund")

    assert ranked[0][0] == chunks["refund"].id


async def test_devanagari_words_are_searchable_as_whole_tokens(session):
    project, _, chunks = await seed(session)

    ranked = await lexical_search.search_chunks(session, project.id, "ट्रैक")

    assert [cid for cid, _ in ranked] == [chunks["hindi"].id]


async def test_dense_channel_finds_a_chunk_with_different_wording(session):
    project, _, chunks = await seed(session)
    retriever = Retriever(FakeEmbedder())

    result = await retriever.search_chunks(session, project.id, "cancellation and return rules")

    assert result.mode == "hybrid"
    assert result.hits[0].chunk_id == chunks["refund"].id
    assert result.hits[0].dense_rank == 1
    assert result.hits[0].bm25_rank is None


async def test_chunk_found_by_both_channels_ranks_first(session):
    project, _, chunks = await seed(session)
    retriever = Retriever(FakeEmbedder())

    result = await retriever.search_chunks(session, project.id, "refund policy")

    top = result.hits[0]
    assert top.chunk_id == chunks["refund"].id
    assert top.bm25_rank == 1 and top.dense_rank == 1
    assert top.rrf_score > result.hits[-1].rrf_score


async def test_bm25_only_fallback_still_returns_hits_and_reports_the_mode(session):
    project, _, chunks = await seed(session)
    retriever = Retriever(UnavailableEmbedder())

    result = await retriever.search_chunks(session, project.id, "refund")

    assert result.mode == "bm25_only"
    assert result.hits[0].chunk_id == chunks["refund"].id
    assert result.hits[0].dense_rank is None
    assert await retriever.mode() == "bm25_only"


async def test_retrieval_never_crosses_project_boundaries(session):
    project_a, source_a, _ = await seed(session)
    project_b, source_b = await make_project(session, "Other")
    foreign = await add_chunk(session, project_b, source_b, 0, "refund refund refund secret other client")
    await session.commit()
    retriever = Retriever(FakeEmbedder())

    result = await retriever.search_chunks(session, project_a.id, "refund")
    other = await retriever.search_chunks(session, project_b.id, "refund")

    assert foreign.id not in {h.chunk_id for h in result.hits}
    assert [h.chunk_id for h in other.hits] == [foreign.id]


async def test_no_matches_returns_an_empty_result_not_invented_evidence(session):
    project, _, _ = await seed(session)
    retriever = Retriever(UnavailableEmbedder())

    result = await retriever.search_chunks(session, project.id, "kubernetes helm charts")

    assert result.hits == []


async def test_hostile_query_syntax_is_neutralised(session):
    project, _, chunks = await seed(session)

    for query in ['refund" OR "x', "NEAR(a b)", "*", "refund AND NOT", ""]:
        await lexical_search.search_chunks(session, project.id, query)

    assert lexical_search.build_match_query('refund" OR "x') == '"refund"'
    assert lexical_search.build_match_query("***") is None


def test_function_words_are_dropped_but_never_leave_an_empty_query():
    assert lexical_search.build_match_query("what is the refund rule") == '"refund" OR "rule"'
    assert lexical_search.build_match_query("refund ka kya rule hai") == '"refund" OR "rule"'
    assert lexical_search.build_match_query("what is the") == '"what" OR "is" OR "the"'


async def test_hit_carries_source_label_and_location(session):
    project, _, chunks = await seed(session)
    retriever = Retriever(UnavailableEmbedder())

    result = await retriever.search_chunks(session, project.id, "doctors")

    hit = result.hits[0]
    assert hit.candidate_type == "chunk"
    assert hit.location["source_label"] == "Clinic chat"
    assert hit.location["ordinal"] == 2
