# docintel-mcp

AI document intelligence for insurance documents, exposed to AI agents as an
[MCP](https://modelcontextprotocol.io) server.

It extracts structured data from certificates of insurance and loss runs, checks
it against deterministic business rules, and routes anything uncertain to a
human reviewer. Agents reach it through four MCP tools; every call is audited.

> All sample documents are synthetic. No real customer data is used anywhere in this repo.

## Status

| Stage | What | State |
|---|---|---|
| 1 | MCP server, typed schemas, rules extractor, validation, audit log, tests | **Done** |
| 2 | Amazon Textract (OCR) + Amazon Bedrock structured output, hybrid with the rules | Next |
| 3 | HTTP transport behind Kong, OAuth scopes per tool, caller identity in the audit log | Planned |
| 4 | Evaluation: per-field precision/recall and cost per document, rules vs. LLM vs. hybrid | Planned |
| 5 | Terraform, Fargate, CloudWatch telemetry, runbook | Planned |

## Architecture

```
agent (Claude Code, etc.)
   │  MCP: stdio today, streamable HTTP behind a gateway in stage 3
   ▼
server.py ── tools: list_documents · extract_document · get_extraction · list_low_confidence_fields
   │            input validation · audit log (one JSON line per call)
   ▼
pipeline.py ── extractor ──▶ fit to schema ──▶ business rules ──▶ status
                  │                                              accepted | needs_review | rejected
                  ├─ extractors/rules.py        (today; the rules-only baseline later)
                  └─ extractors/textract_bedrock.py   (stage 2)
   ▼
store.py ── one JSON result per document id (content hash, so re-runs are idempotent)
```

Key design points:

- **One schema, many extractors.** `schemas.py` defines each document type once. Rules, LLM and
  hybrid extractors all have to produce it, which is what makes them comparable in stage 4.
- **Rules after the model, always.** Arithmetic, date order and identifier formats are checked in
  `validation.py` no matter which extractor ran.
- **Confidence drives human review.** Any field under `REVIEW_THRESHOLD` (0.80), or any rule
  failure, sets the status to `needs_review`.
- **Tool arguments are untrusted.** Tools accept a document *name* from an allow-listed inbox,
  never a path. Ids are format-checked before they touch the filesystem.

## Quick start

Requires [uv](https://docs.astral.sh/uv/). uv installs Python 3.12 itself if it is missing.

```bash
uv sync               # creates .venv and installs the locked dependencies, dev tools included
uv run pytest         # 15 tests, including end-to-end calls through the MCP protocol
uv run ruff check .
```

Add a dependency with `uv add <package>` (or `uv add --dev <package>`); commit `uv.lock` with it.

### Use it from Claude Code

A project-level `.mcp.json` is included, so starting `claude` in this folder offers the
`docintel` server. To add it by hand instead:

```bash
claude mcp add docintel -- uv run --directory "$(pwd)" docintel-mcp
```

Then try:

> List the documents, extract `loss_run_002_bad_total.txt`, and tell me what a reviewer needs to check.

### Inspect the tools by hand

```bash
npx @modelcontextprotocol/inspector uv run docintel-mcp
```

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `DOCINTEL_INBOX` | `samples` | Folder the tools may read documents from |
| `DOCINTEL_DATA` | `.data/results` | Where extraction results are stored |
| `DOCINTEL_AUDIT_LOG` | `.data/audit.jsonl` | Audit trail, one JSON line per tool call |

## Samples

| File | Shows |
|---|---|
| `coi_001.txt` | Clean certificate → `accepted` |
| `coi_002_messy.txt` | Non-standard labels, odd policy number, no holder → `needs_review` |
| `loss_run_001.txt` | Clean loss run, three claims → `accepted` |
| `loss_run_002_bad_total.txt` | Stated total does not match the claims → caught by a rule |

## Docs

- `docs/adr/` – architecture decision records
- `docs/threat-model.md` – threats specific to exposing tools to AI agents
- `NOTES.md` – running log of decisions and surprises

## License

MIT. See `LICENSE`.
