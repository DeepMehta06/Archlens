# ArchLens backend evaluation

Live evaluation of the backend against real `gemma4:e4b` and `embeddinggemma` (Ollama 0.40.2, RTX 4060 Laptop 8 GB, Windows 11, thinking off). Runs on 2026-10-11 (two rounds; round 3 below is the current state). Harness: `backend/evals/run_evals.py`, data: `backend/evals/datasets/`, raw output: `backend/evals/results/latest.json`.

```bash
cd backend
python -m evals.run_evals            # all suites, --repeat N for extraction/router repeats
python -m evals.run_evals router     # one suite
```

## Read this first: how far to trust these numbers

- The datasets are small and **synthetic, written by the developer**: 8 conversations, 37 router messages, 35 retrieval queries, 8 change requests. They show behaviour and catch regressions; they are not real-world accuracy. There are no confidence intervals and no comparison against another model or human annotators.
- **Dev vs held-out.** `clinic`, `bakery`, `gym` were used while tuning prompts. `salon` and `school` were held-out in round 2 but then tuned against, so they now count as dev (`split_note` in the manifest). `travel`, `ngo`, `logistics` and 15 retrieval queries were written afterwards and **not tuned on**. One caveat: I read their baseline results before making round-3 changes, and the small-talk prompt rule was prompted by the "chai" miss in `ngo`. They are cleaner than dev, not perfectly clean.
- The router set was extended after its first failure, so it is a dev set.
- Matching is keyword-based (an item "finds" a fact if its title or description contains the keywords). It can over- and under-credit; one "miss" in round 3 was the model writing "one lakh", which was a matcher gap and was fixed in the dataset, not the model.
- Runs are stochastic. Extraction was repeated 2 to 3 times; retrieval scores shifted slightly between runs.

## Results (round 3, current)

### Extraction (2 repeats)

| Metric | Dev (5 conv., 78 facts over 2 runs) | Held-out (3 conv., 42 facts over 2 runs) |
|---|---|---|
| Planted facts found | 75/78 | **42/42** |
| Hedged statements kept and not marked explicit | 11/14 | **6/6** |
| Planted gaps raised as a client question | 11/12 | **6/6** |
| Traps triggered (small talk, superseded or excluded items) | 1 | **0** |
| Evidence links verified against stored text | 86/86 | 48/48 |
| Every item `needs_review` | yes | yes |
| Failed jobs | 0 | 0 |
| Mean time per conversation | 11.5 s | 10.5 s |

Remaining failure modes (all on dev conversations):
- A hedged "maybe later" idea is sometimes omitted entirely (bakery logo; school image uploads).
- A reversed requirement (Google Calendar sync dropped) reappeared once as an item.
- One run missed the budget question.
- A hedge on one part of a sentence can be applied to the whole item.
- Recording an explicit exclusion ("cafeteria is out of scope") as an item is counted as a trap by the eval, but is arguably useful in a scope ledger; that is a design choice, not a clear bug.

### What changed and the measured effect

| Change | Measured effect |
|---|---|
| Router prompt: ambiguous short fragments default to `answer_question` | 33/37 (2 off-topic false positives such as "appointment reminders") to 37/37; 74/74 in the latest two-repeat run (dev set) |
| Extraction prompt: keep hedged ideas as tentative; add a question for undecided topics; keep only the final version of reversed statements; skip small talk | Round 2 held-out: 45/48 facts, 4/6 gap questions, 2 traps. Round 3 fresh held-out: 42/42, 6/6, 0 traps (see caveat above) |
| **Code-level guarantee**: every newly created tentative item with no related model question gets a templated "Can you confirm this point: ..." question (`questions_from_hedges` in the job result) | Removes reliance on the model remembering to ask; covered by a unit test |
| BM25 function-word filter (English and Hinglish) | Hybrid recall@3 0.80 to 0.90 in round 2 (single runs) |
| RRF dense-channel weight 1.0 to 2.0 (`RRF_DENSE_WEIGHT`) | Held-out MRR 0.88 to 0.92; dev flat (0.725 to 0.731) |

### Router (37 messages, 2 repeats)

74/74 correct, 0 off-topic false positives, median 0.5 s. Dev set (see caveats).

### Retrieval (8 conversations, 300-character chunks, dense weight 2.0)

| Split | Mode | recall@3 | MRR |
|---|---|---|---|
| Dev (n=20) | BM25 | 0.65 | 0.63 |
| Dev | Dense | 0.80 | 0.77 |
| Dev | Hybrid | 0.75 | 0.73 |
| Held-out (n=15) | BM25 | 0.67 | 0.58 |
| Held-out | Dense | 1.00 | 0.93 |
| Held-out | Hybrid | 0.93 | 0.92 |

**Honest reading:** BM25 is strong when a query reuses source words (Hinglish included) and weak on paraphrase. Weighting dense higher closed most of the held-out gap, but **dense alone is still slightly ahead of hybrid** (about one query at this size). Hybrid is kept because lexical match protects exact terms, numbers and names, and because it is the fallback when embeddings are unavailable; a reranker is the next experiment.

### Change detection

Primary classification 8/8 on 8 clear-cut requests against a 9-item baseline (about 2 s each). The `unclear` class is untested.

### Invariants

No item auto-approved; every item has evidence; all 10 verified quotes occur verbatim in the stored text (Devanagari conversation included). Also enforced by unit tests with a faked model.

### File import (PDF, image, audio): live tests through the HTTP API, not an accuracy eval

Files were generated by me, but degraded to look more like real captures, and uploaded to the running server (transcribe, chunk, extract, cite):

| File | Result |
|---|---|
| Phone-style WhatsApp screenshot (bubbles, blur, 2.5 degree rotation, noise, JPEG quality 35) | All 5 lines transcribed exactly; 4 items and 1 question; quotes marked `transcript_quote` (27 s total) |
| Devanagari plus Latin handwritten-note style image (rotated, blurred JPEG) | All 4 lines transcribed (one spelling variant: अंग्रेज़ी as अंग्रेजी); 4 items (7 s) |
| 44-second 8 kHz noisy synthesized English voice note | Complete punctuated transcript after the fixes below; 8 items, deadline/budget/payment explicit, corporate accounts and refund window tentative; two recognition slips ("customers report chat", "receipt" for "receipts") (19 s) |
| 3-page text-layer PDF | Text layer used, no model call; 6 items (9 s) |
| 3-page scanned PDF | Vision fallback; 6 items (29 s) |

Defects found and fixed during this test:
- **Hard 25-second audio cuts dropped a sentence**, and the unpunctuated transcript became one giant unit, so one "maybe" wrongly marked the firm deadline, budget and payment items tentative (3 false hedge downgrades). Now segments are cut at the quietest 100 ms and the model is asked for one punctuated sentence per line; the same file then produced 0 false downgrades.
- **Ollama returned HTTP 500 (out of memory loading the multimodal projector)** on image and audio calls while the text and embedding models were resident and other work shared the 8 GB GPU; one text PDF extraction also failed in that unstable state. Calls succeeded once models were unloaded. A retry that unloads the models was added (`OllamaClient.unload_all`), **but it did not trigger in the later successful runs, so it is untested against a real failure**; the original failure was not reproducible on demand.

Still untested: real phone photos and screenshots, real voices and accents, Hinglish speech (no Hindi TTS voice was available), handwriting, long recordings, formats other than WAV.

## Not evaluated

long conversations beyond one extraction batch, chat answer quality (only citation grounding is checked by tests), draft-message language quality, diagram correctness, large-project retrieval, other models.
