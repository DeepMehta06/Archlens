# ArchLens backend evaluation

Live evaluation of the backend against real `gemma4:e4b` and `embeddinggemma` (Ollama 0.40.2, RTX 4060 Laptop 8 GB, Windows 11, thinking off). Run on 2026-10-11. Harness: `backend/evals/run_evals.py`, data: `backend/evals/datasets/`, raw output: `backend/evals/results/latest.json`.

```bash
cd backend
python -m evals.run_evals            # all suites, --repeat N for extraction/router repeats
python -m evals.run_evals router     # one suite
```

## Read this first: how far to trust these numbers

- The datasets are small and **synthetic, written by the developer** (5 conversations, 37 router messages, 20 retrieval queries, 8 change requests). They show behaviour and regressions, not real-world accuracy. There is no confidence interval, and no comparison against another model or human annotators.
- Two extraction prompt edits and a retrieval change were made **after seeing failures on the first three conversations ("dev")**. Dev scores are therefore optimistic. Two further conversations (`salon`, `school`) were written afterwards and not tuned against; **the held-out numbers are the ones to quote.**
- The router set was extended after the first failure was seen, so it is also a dev set.
- Matching is keyword-based (an extracted item "finds" a planted fact if its title/description contains the keywords), which can both over- and under-credit.
- Runs are stochastic. Extraction was repeated 3 times; retrieval embedding scores varied slightly between runs (hybrid MRR 0.72 to 0.77).

## Results

### Extraction (3 repeats per conversation)

| Metric | Dev (3 conv., 69 facts) | Held-out (2 conv., 48 facts) |
|---|---|---|
| Planted facts found | 69/69 | **45/48 (94%)** |
| Hedged statements kept and not marked explicit | 12/12 | **6/9** |
| Planted gaps raised as a client question | 12/12 | **4/6** |
| Hallucination/superseded/out-of-scope traps triggered | 0 | **2** |
| Evidence links verified against stored text | 78/78 | 51/51 |
| Every item `needs_review` | yes | yes |
| Failed jobs | 0 | 0 |
| Mean time per conversation (12 to 15 messages) | 11.8 s | 11.2 s |

Held-out failure modes seen:
- A hedged "maybe later" idea (school: images for homework) is sometimes omitted entirely instead of becoming a tentative item.
- An undecided topic sometimes becomes a tentative item without a matching client question, and the number of questions varies between runs (one salon run raised none).
- Out-of-scope chatter (a cafeteria menu) was recorded as an item in one of three runs.
- A hedge on one part of a sentence can be applied to the whole item (homework upload marked tentative).

### Effect of the changes made during this evaluation

| Change | Before | After |
|---|---|---|
| Router prompt: ambiguous short fragments default to `answer_question` | 33/37 (2 off-topic false positives, e.g. "appointment reminders") | 37/37, later 111/111 over 3 repeats (dev set) |
| Extraction prompt: keep hedged ideas as tentative; add a question for undecided topics; keep only the final version of reversed statements | dev facts 40/46, hedges kept 2/8 | dev facts 69/69, hedges 12/12 (see held-out above for the realistic figure) |
| BM25 function-word filter (English and Hinglish) | hybrid recall@3 0.80, MRR 0.72 | recall@3 0.80 to 0.90, MRR 0.72 to 0.77 across runs |

An intermediate prompt version that only said "do not omit hedged statements" raised hedge capture but dropped the refund question and re-introduced a superseded requirement; that is why the question and reversal rules were added.

### Router (37 messages x 3 repeats, English and Hinglish, 7 intents)

111/111 correct, 0 off-topic false positives, median latency 0.53 s. Dev set (see caveats).

### Retrieval (11 chunks of about 300 chars across 5 conversations, 20 queries, final run)

| Mode | recall@1 | recall@3 | MRR |
|---|---|---|---|
| BM25 | 0.55 | 0.65 | 0.60 |
| Dense (EmbeddingGemma) | 0.70 | 0.90 | 0.80 |
| Hybrid (RRF, k=60) | 0.60 | 0.80 | 0.72 |

By query type (recall@3 / MRR): English direct (n=3) all modes 1.0; Hinglish direct (n=6) all modes 1.0 / 1.0; English paraphrase (n=11): BM25 0.36 / 0.32, dense 0.82 / 0.70, hybrid 0.64 / 0.56.

**Honest reading:** BM25 is strong when the query reuses source words (including Hinglish) and weak on paraphrase. Dense search beat the equal-weight hybrid on this set, so the fusion is currently not adding value over dense alone; with n=20 the gap is a handful of queries, but the direction was consistent across runs. Weighted fusion or a reranker is the obvious next experiment and was **not** tried, to avoid tuning on 20 queries.

### Change detection (8 requests against a 9-item clinic baseline)

Primary classification 8/8 (already covered 2/2, contradiction 3/3, new requirement 3/3). Each call took about 2 s. Tiny set; all cases are clear-cut, and the `unclear` class is untested.

### Invariants

On a Devanagari-containing Hinglish conversation: no item was auto-approved, every item has evidence, all 10 verified quotes occur verbatim in the stored chunk text. These properties are also enforced by unit tests with a faked model.

## Not evaluated

Image/audio/PDF (not implemented), long conversations beyond one extraction batch, chat answer quality (only citation grounding is checked by tests), draft-message language quality, diagram correctness, multi-user or large-project retrieval, comparison with other models.
