# Security policy

## Supported versions

Only the `main` branch is supported. There are no releases yet; fixes land on `main`.

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub's private vulnerability reporting:
<https://github.com/zhengyixu/docintel-mcp/security/advisories/new>

Do not open a public issue for a security problem. Include what you did, what happened, and
what you expected, ideally with a minimal reproduction against the synthetic samples.

## Scope

In scope:

- The MCP tools exposed by the server (`list_documents`, `extract_document`, `get_extraction`,
  `list_low_confidence_fields`): argument validation, error messages and what they reveal.
- Path handling: reading anything outside the allow-listed inbox, for example through traversal,
  symlinks or crafted document ids.
- The audit log: missing records, or sensitive data (document text, extracted values) ending up in it.
- Prompt injection through documents: document content that changes what the system or the
  calling agent does.

Out of scope: vulnerabilities in third-party dependencies with no demonstrated impact on this
project (report those upstream), and findings that require an already compromised host.

Known, unfixed issues are tracked in the "Review backlog" in [`NOTES.md`](NOTES.md). The threats
this project considers, and the status of each mitigation, are in
[`docs/threat-model.md`](docs/threat-model.md).

## Data

All sample documents in this repository are synthetic. No real customer or personal data is used
anywhere. If you find something that looks like real personal data, please report it as above.

## Response expectations

This is a personal portfolio project maintained by one person. Reports are handled on a
best-effort basis: I aim to acknowledge a report within a week, but there is no guaranteed
response or fix time, and no bug bounty.
