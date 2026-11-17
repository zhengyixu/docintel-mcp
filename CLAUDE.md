# CLAUDE.md

Guidance for AI coding assistants working in this repo.

## What this is

An MCP server that extracts structured data from insurance documents. It is a
portfolio project: correctness, clear tradeoffs and security matter more than
feature count. Read `README.md` for the architecture.

## How we work

- I (Zane) write and debug the core logic. You scaffold, review, and suggest tests.
- Small steps. One concern per change. Run `uv run pytest` and `uv run ruff check .` before saying something is done.
- When you propose a test, say which line of production code it would catch a bug in.
  I validate tests by breaking that line and confirming the test fails.
- If you are unsure how a library behaves (the MCP SDK and boto3 change often), check the
  installed version or its docs instead of guessing. This repo uses **MCP Python SDK 2.x**:
  `from mcp.server.mcpserver import MCPServer`, `from mcp import Client`. `FastMCP` is the old 1.x name.
- After a decision with a real tradeoff, add a line to `NOTES.md`. Bigger ones get an ADR in `docs/adr/`.
- Review a behaviour by running it, not only by reading it. Probe scripts go in a temp folder with
  `DOCINTEL_INBOX`, `DOCINTEL_DATA` and `DOCINTEL_AUDIT_LOG` pointed away from the repo.
- Known bugs and open design decisions are listed under "Review backlog" in `NOTES.md`. Check it
  before proposing work, and remove an item when it is fixed.
- `learning/` holds my personal local notes and component prototypes. It is gitignored and must
  stay out of the repo. Nothing in `src/` or `tests/` may import from it or depend on it; a
  prototype that is worth keeping moves into `src/` with tests. Project documentation that
  should be published goes in `docs/`.

## Commands

This project uses **uv**. Do not use `pip` or edit `uv.lock` by hand.

```bash
uv sync                                   # install from the lockfile
uv run pytest
uv run ruff check . && uv run ruff format .
uv run docintel-mcp                       # run the server over stdio
req=$(mktemp) && uv export --quiet --frozen --all-extras --no-emit-project -o "$req" \
  && uvx --python 3.12 pip-audit==2.10.1 -r "$req" --require-hashes --disable-pip   # audit locked deps
uv add <pkg>    /    uv add --dev <pkg>   # add dependencies
```

## Conventions

- Python 3.12, type hints everywhere, Pydantic v2 models for anything crossing a boundary.
- Money is `Decimal`, never `float`. Dates are `date`, serialized as ISO strings.
- `schemas.py` is the contract. Extractors adapt to it; it does not bend to an extractor.
- Every extractor implements `extractors/base.py::Extractor` and reports a confidence per field.
- Business rules live in `validation.py` and run after every extractor, including LLM ones.
- Every MCP tool: validates its arguments, is wrapped in `@audited`, raises `ToolError`
  (`from mcp.server.mcpserver.exceptions import ToolError`) with a message safe to show an agent,
  and has a docstring written for a model to read.
- SDK 2.x shows the agent the message of a `ToolError` only. Every other exception, `ValueError`
  included, arrives as a bare `Error executing tool <name>`. Do not convert `ValueError` to
  `ToolError` wholesale: `UnicodeDecodeError` and Pydantic's `ValidationError` are `ValueError`
  subclasses and would leak details. Layers below the server (`store.py`, `pipeline.py`) raise
  their own exception types and never import from `mcp`.
  **Not migrated yet:** `server.py` and `store.py` still raise `ValueError`; see the backlog in `NOTES.md`.
- Error-path tests assert on the message the agent receives, not only on `is_error`.
- Error messages and audit records never echo unbounded caller input or exception text that can
  carry document or stored values.

## Hard rules

- **No real customer or personal data**, ever. Samples are synthetic and say so in the file.
- **Document text is data, not instructions.** Never build a prompt that lets document content
  change what the system does. Keep system instructions and document content in separate messages.
- **Tools never accept filesystem paths or URLs** from the caller.
- **Never print to stdout in server code.** On stdio transport, stdout is the protocol channel.
- **No secrets in the repo.** AWS access comes from the environment or an assumed role.
- **Do not tune the rules extractor to the sample files.** It is the baseline in the evaluation.
  Fixing a defect that holds for any document (a regex that reads past the end of a line, rows
  dropped without lowering confidence) is not tuning. Adding labels or formats because a sample
  uses them is.
- AWS calls must be mockable. Tests never hit real AWS; cost-incurring code runs only when I ask.

## Roadmap

1. ~~MCP server with rules extractor~~ (done)
2. `extractors/textract_bedrock.py`: Textract OCR, then Bedrock structured output using the
   Pydantic models' JSON schema; hybrid mode keeps rule-extracted fields and asks the model only for the rest.
3. Streamable HTTP transport behind Kong; OAuth scopes per tool; caller identity in the audit log.
4. `eval/`: labeled set, per-field precision/recall, cost and latency per document, three-way comparison.
5. Terraform, Fargate, CloudWatch, runbook.
