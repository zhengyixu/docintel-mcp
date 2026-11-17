# ADR 0001: One schema, interchangeable extractors, rules always run last

- Status: accepted
- Date: 2026-11-16

## Context

Insurance documents arrive in many layouts. Some fields are easy to pull with rules; others need
OCR and a language model. We need to compare approaches fairly, keep costs visible, and never let
a fluent but wrong extraction through.

## Options considered

| Option | Pros | Cons | Cost / risk |
|---|---|---|---|
| Rules only | Free, fast, fully explainable | Breaks on unfamiliar layouts | Lowest cost; coverage risk |
| LLM only | Handles layout variety | Costs per document; can be confidently wrong on arithmetic and ids | Highest cost; accuracy risk |
| Hybrid behind one schema | Each field handled by the cheapest method that works; approaches are measurable against each other | More moving parts | Middle cost; lowest accuracy risk |

## Decision

Define each document type once as a Pydantic model. Every extractor implements one interface and
reports a confidence per field. Deterministic business rules run after every extractor. Low
confidence or any rule failure sends the document to human review.

## Evidence

To be filled in from stage 4: per-field precision/recall and cost per document for all three options.

## Consequences

- Adding an extractor does not touch the MCP tools or the rules.
- The rules extractor doubles as the evaluation baseline, so it must not be tuned to the samples.
- Revisit if the hybrid's extra accuracy does not justify its cost over rules-only for a document type.
