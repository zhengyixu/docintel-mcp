# Notes

Running log of decisions and surprises. Newest first. One or two lines each.

## 2026-11-17

- Security phase 1: actions pinned to commit SHAs (a moved tag cannot change CI) at the cost of manual bumps,
  so Dependabot updates them weekly, minor/patch grouped; pip-audit runs on `uv export --all-extras` with
  `--require-hashes`, auditing exactly the locked set (including the `aws` extra) without resolving again,
  but CI now fails on any new advisory, even one in a dev-only dependency.

## 2026-11-16 (review)

Two full reviews of stage 1. The second one ran the edge cases instead of only reading the code,
and that is what found the three bugs. Nothing below is fixed yet; see "Review backlog".

- Surprise: MCP SDK 2.3 shows the agent the message of a `ToolError` only. Our `ValueError`
  messages ("Unknown document", "No extraction found") arrive as `Error executing tool <name>`.
  The tests missed it because they assert `is_error` and never the text.
- Decision (proposed, not implemented): tools raise `ToolError` for anticipated failures;
  `store.py` raises its own exception type and stays free of `mcp` imports. Rejected the
  alternative of translating every `ValueError` in `@audited`, because `UnicodeDecodeError` and
  Pydantic's `ValidationError` subclass `ValueError` and would leak codec details and stored values.
- Surprise: in a regex, `\s*` matches newlines. `_find` therefore reads the next line when a label
  has no value, and reports it at 0.95.
- Surprise: a claim row the regex cannot read disappears without lowering confidence. The total
  rule only catches it when the lost row carries money.
- Lesson: "rules after the model" protects against wrong values, not against values the extractor
  never produced. Coverage needs its own signal.
- `learning/` added for personal local notes and component prototypes. Gitignored; published documentation stays in `docs/`.

## 2026-11-16

- Switched from pip/venv to uv: one lockfile (`uv.lock`), `uv sync --locked` in CI, much faster installs.
- Started on MCP Python SDK 2.x. `FastMCP` was renamed `MCPServer`; most tutorials online still show 1.x.
- Document id is a content hash, so extracting the same document twice overwrites one result instead of creating two.
- Tools take a document name from an allow-listed folder, not a path. An agent can be talked into
  passing `../../anything`, so the server has to be the one that refuses.
- Rules-extractor confidence is coarse on purpose: 0.95 primary label, 0.70 alias, 0.30 found but unparseable, 0 missing.
- `loss_run_002_bad_total.txt` is the demo for "rules after the model": the document is perfectly
  readable and still wrong, and only arithmetic catches it.

## Review backlog

Open items from the 2026-11-16 review, most important first. Delete a line when it is fixed.

Bugs (reproduced):

- `server.py:52,56,58,91,101`, `store.py:24`: error messages never reach the agent (`ValueError`, not `ToolError`).
- `rules.py:80`: `\s*` after the colon crosses newlines. A blank `Insured:` yields the next line at 0.95, status `accepted`.
- `rules.py:113`: unreadable claim rows are dropped silently. A zero-incurred row with status `Reopened` vanished; result `accepted`.

Audit log:

- `audit.py:33`: `str(exc)` can carry stored values (a corrupted result file logged `input_value=...`). Hole in threat #9.
- `audit.py:39`, `store.py:24`: no size limit. A 5,000-character id made a 10 KB record.
- `audit.py:39`: only keyword arguments are logged; a positional call logs `{}`.
- The record does not say which `document_id` or status a call produced.

Missing rules (both `accepted` today):

- Loss date outside the policy period.
- Duplicate claim numbers.

Smaller:

- `server.py:66`: `list_documents` lists files that `extract_document` refuses (symlinks, oversize, non-UTF-8).
- `validation.py:18`: `_dates_in_order` has no type hints.
- The folder is not a git repository yet, so CI has never run. `.claude/settings.local.json` is not gitignored.
- `docs/threat-model.md`: #9 is marked done but has the hole above; #8 claims idempotent re-runs
  limit cost, but `extract_document` always re-extracts.

Tests to write (line each one guards):

- Error text reaches the agent: `server.py:52`, `:56`, `:91`. Fails today.
- Crash details stay on the server (non-UTF-8 file): guards a careless `ValueError` → `ToolError` translation.
- Blank label does not take the next line: `rules.py:80`.
- Unreadable claim row lowers `claims` confidence below 0.80: `rules.py:113`.
- Oversize file refused: `server.py:57`.
- Symlink out of the inbox refused: `server.py:55`.
- `loss_before_valuation`: `validation.py:93`. `closed_claim_reserve`: `validation.py:102`.
  `aggregate_at_least_occurrence`: `validation.py:56`.

## Open questions

- An unparseable optional field rejects the whole document (`General Aggregate: $2M` → `rejected`,
  `pipeline.py:31`). Drop the field and return `needs_review` instead?
- Duplicate labels: the first match wins at 0.95. Real certificates list several policies and the
  schema models one. Model a list of policies, or state the limit in the README?
- The document id hashes the text only (`pipeline.py:20`), so rules, LLM and hybrid results for one
  document overwrite each other. Add the extractor name to the id, or key the store on both?
- Should `extract_document` return the stored result when one exists, so a loop cannot spend model
  money twice on the same document?
- Hybrid mode: ask the LLM only for fields the rules missed, or ask for everything and compare?
- What confidence should an LLM-extracted field get? (Self-reported confidence is unreliable; consider
  agreement between two passes, or rule agreement, instead.)
- Review threshold of 0.80 is a guess. Set it from the evaluation data.
