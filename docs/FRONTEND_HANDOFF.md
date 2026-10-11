# ArchLens: backend handoff for the frontend

Backend v0.2 is complete for text and WhatsApp input, has 82 passing tests, and has been run end to end on live `gemma4:e4b`. The existing `frontend/` is the old v1 UI and **does not match this API**; rebuild it, do not patch it.

Base URL `http://127.0.0.1:8000`, all routes under `/api`, interactive docs at `/docs`. CORS allows `http://localhost:5173` and `http://127.0.0.1:5173` (`ALLOWED_ORIGINS`). Start with `uvicorn app.main:app --port 8000` from `backend/`. Vite dev server on 5173.

## What the product is

Paste or upload a messy client conversation (English, Hinglish, WhatsApp export). Gemma extracts **ledger items** (requirement, constraint, decision, assumption). Every item cites the exact source words. Items also produce **questions** for the client. The user reviews and approves items, freezes an immutable **snapshot** (baseline), and later compares a new client request against it. A project-scoped **chat** drives all of this.

Layout decided with the user: chat-first. Chat in the centre, workspace panel on the right (tabs: Ledger, Diagrams, Questions, Baseline, Evidence), sources rail on the left. Light theme, glassmorphic, plus a good landing page.

## Rules the UI must respect (these are product claims)

1. **The model never approves scope.** New items are always `approval_status: needs_review`. Only a user click calls `PATCH /ledger-items/{id}` with `approved`. Chat never approves, rejects or snapshots. Do not add a chat shortcut for it.
2. **Approval and evidence certainty are separate fields.** `approval_status` (needs_review, approved, rejected) is the user's decision. `evidence_status` (explicit, tentative, inferred, unknown) is how firmly the client said it. Show them as two distinct badges.
3. **Quotes are code-rebuilt and verified.** Show `verification_status` and `evidence_verified / evidence_total` honestly. Do not style an `unverified` quote like a verified one.
4. **Hedged statements are capped at `tentative`**, with a note in `verification_note`. Surface the note.
5. **`grounded:false` on a chat answer means no valid citation.** Mark it visibly (for example "not backed by a source").
6. **Draft client messages are editable**, not auto-sent. Nothing is ever sent anywhere.
7. **Snapshots are immutable.** No edit or delete UI for them.
8. Be honest in copy: runs on local Ollama, no cloud AI. Do not claim "zero network" or invent accuracy numbers.

## Enums

- item_type: `requirement | constraint | decision | assumption` (display ids `REQ-n`, `CON-n`, `DEC-n`, `ASM-n`)
- evidence_status: `explicit | tentative | inferred | unknown`
- approval_status: `needs_review | approved | rejected`
- risk_level: `low | medium | high`
- stated_by / speaker_role: `client | you | unknown`
- verification_status: `verified | unverified | not_applicable`
- evidence_kind: `text_quote | transcript_quote | visual_observation` (only `text_quote` is produced today)
- question priority: `low | medium | high`; status: `open | resolved | dismissed`
- source status: `uploaded | processing | processed | failed`; source_type: `text | whatsapp | image | audio | pdf` (only text and whatsapp are produced today)
- job status: `queued | processing | completed | failed`
- change classification: `already_covered | new_requirement | contradiction | unclear`
- diagram_type: `architecture | sequence | er | component | requirements`

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | `{status, version, ollama_reachable, model, model_installed, embed_model, embed_model_installed, retrieval_mode ("hybrid"/"bm25_only"), fts5, privacy, error}`. Use for a status pill. |
| POST | `/projects` | `{name, description?, my_name?}` |
| GET | `/projects`, `/projects/{id}` | |
| PATCH / DELETE | `/projects/{id}` | delete is 204, removes data and search index |
| GET | `/projects/{id}/sources` | |
| POST | `/projects/{id}/sources` | `{text, label?, me?, analyze=true}` returns `{source, job}` |
| POST | `/projects/{id}/sources/upload` | multipart `.txt`/`.md` (WhatsApp exports), returns `{source, job}` |
| GET | `/projects/{id}/sources/{sid}` | source with chunks (`units_json` = numbered messages with sender and time) |
| PATCH | `/projects/{id}/sources/{sid}` | `{me}`: which sender is "you" (needed when WhatsApp sender detection is ambiguous) |
| GET | `/jobs/{id}` | `{status, stage, progress 0-100, error_message, result_json}`. Poll about every 1 s while `queued/processing`. Real stages, not fake. Demo import takes about 28 s. |
| GET | `/projects/{id}/ledger` | query `status`, `type`, `evidence_status`; items include `evidence_total`, `evidence_verified`, `open_questions` |
| GET | `/ledger-items/{id}` | adds `evidence[]` (quote, highlight, unit_numbers, speaker, speaker_role, verification_status, verification_note, source_label, full `chunk` with surrounding messages) and `questions[]` |
| PATCH | `/ledger-items/{id}` | any of `title, description, item_type, evidence_status, approval_status, risk_level` |
| GET | `/projects/{id}/questions` | default `status=open` |
| PATCH | `/questions/{id}` | `{status, resolution_note}` |
| POST | `/projects/{id}/draft-message` | `{language: "english"|"hinglish", question_ids?}` returns `{language, text, question_ids}` |
| POST / GET | `/projects/{id}/snapshots` | create `{label?}` from approved items only; `snapshot_json` holds the frozen items; `version` increments |
| POST | `/projects/{id}/compare` | `{snapshot_id, incoming_text}` returns a ChangeReport |
| GET | `/change-reports/{id}` | `results[]: {incoming_claim, classification, related_display_ids, related_baseline_item_ids, supporting_chunk_ids, explanation, confidence, candidate_item_id}`, plus `draft_message` (always null today: compare does not generate one; use `/draft-message`) |
| POST / GET | `/projects/{id}/diagrams` | create `{diagram_type, focus?}`; returns `{mermaid_source, title, warnings_json[]}`. Render with mermaid.js. Show `warnings_json` (dropped dangling references). |
| GET | `/projects/{id}/export.md` | Markdown scope brief, `text/markdown`, has a filename header |
| POST | `/projects/{id}/chat` | SSE stream, below |
| GET | `/projects/{id}/chat/messages?thread_id=` | history: `{role, content, citations_json, cards_json}`. Render stored cards from `cards_json` the same way as live ones. |
| POST | `/demo/seed` | creates (or returns) the labelled "Pune Clinic App (demo data)" project, runs ingestion in the background. Returns `{project, sources, job, compare_example, created}`. `compare_example` is a ready-made incoming request for the compare demo. |

Errors: Ollama problems come back as a structured error from the `OllamaError` handler; render the `detail` message, do not swallow it.

## Chat stream (the core of the UI)

`POST /api/projects/{id}/chat` with `{message, thread_id?}`. Use `fetch` + a stream reader (not `EventSource`, it is POST). Frames are `event: <type>\ndata: <json>\n\n`; the JSON always has a `type`.

| type | payload | UI |
|---|---|---|
| `thread` | `thread_id`, `user_message_id` | keep `thread_id` and send it on later turns |
| `status` | `stage`: routing, searching, writing, drafting, drawing, comparing (writing also has `retrieval_mode`) | typing/progress indicator with the stage name |
| `token` | `text` | append to the assistant bubble |
| `replace` | `text` | replace the whole bubble text (citation markers were cleaned) |
| `card` | `card` (see below) | render a rich card under the message |
| `citations` | `citations[]`, `grounded` | citation chips |
| `error` | `message` | inline error |
| `done` | `message_id`, `grounded` | end of turn |

Citation objects: chunk kind `{marker:"C1", kind:"chunk", chunk_id, source_id, source_label, snippet}`; ledger kind `{marker:"L1", kind:"ledger_item", ledger_item_id, display_id, snippet}`. Answer text contains `[C1]`/`[L1]` markers; map them to chips. Clicking one should open the Evidence tab at that chunk/item.

Card types:
- `ledger_list`: `items[{id, display_id, title, item_type, evidence_status, approval_status, stated_by, evidence_total, evidence_verified}]`
- `questions`: `questions[{id, question, reason, priority, ledger_item_id}]`
- `draft_message`: `{language, text, question_ids}` (editable textarea, copy button)
- `diagram`: `{diagram_id, diagram_type, title, mermaid_source, warnings[]}`
- `change_report`: `{report_id, snapshot_label, results[]}` (same result shape as above)
- `confirm_add_source`: `{preview, char_count, looks_like_whatsapp}`. A long paste or a WhatsApp-looking paste is NOT analysed automatically; the UI must show "Add as source and analyze?" and, on yes, call `POST /sources`. Then poll the job.
- `error`: `{message}`

Router intents behind chat: answer_question, list_ledger, draft_message (English or Hinglish), create_diagram, compare_request, open_questions, off_topic.

Latency observed (one machine, RTX 4060 8 GB, single runs): chat turn about 2 s, router 0.6-1.1 s, diagram about 3 s, compare 2-3 s, draft about 1 s, demo import 28 s. Stream tokens and show status stages; do not fake progress.

## Suggested flows to design for

1. Landing page, then "Try the demo" calls `/demo/seed`, shows real job progress, then lands in the workspace with the demo project.
2. New project, paste or upload chat, confirm "which sender is you", watch real ingestion stages.
3. Review: ledger list, open an item, see verified quotes highlighted inside the surrounding messages, approve/reject/edit.
4. Questions, then "Draft message" in English or Hinglish.
5. Create snapshot (v1), then paste a new client request into compare, see classified results with links back to baseline items.
6. Diagram from the ledger; export brief.
7. Chat available throughout.

## Seed data

`POST /api/demo/seed` is the fastest way to get realistic data (Hinglish clinic-app chat: 7 items, 2 questions, all quotes verified in the last run). The demo project is labelled as demo data everywhere; keep that label visible.

## Known limitations (do not design around features that do not exist)

- No image, audio or PDF import yet (planned).
- No auth, single local user.
- Extraction can miss items (the refund policy became a question, not an item, in the demo run). Duplicate detection is title similarity only.
- `embeddinggemma` is installed and `/health` reports `retrieval_mode: "hybrid"`. Only ad hoc live checks so far; no retrieval quality numbers.
- Extraction quality has not been formally evaluated; do not show accuracy figures.

## Frontend requirements from the user (CLAUDE.md, compulsory)

Use, in order: Anthropic `frontend-design` skill, Impeccable skill, shadcn MCP (primary component source) and the page-guide-design MCP. Verify at the start that each is actually loaded and tell the user if one is missing; do not skip silently. Do not mix FlyonUI with shadcn. As of 2026-10-11 the shadcn and page-guide-design MCPs were not connected in the backend session. Light, glassmorphic, good landing page. Ask the user for their screen picture/reference before designing.
