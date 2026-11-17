"""End-to-end tests through the MCP protocol, using an in-process client."""

import json

import pytest
from mcp import Client

from docintel.server import mcp


def payload(result):
    assert not result.is_error, result.content
    return json.loads(result.content[0].text)


async def test_server_exposes_the_expected_tools():
    async with Client(mcp) as client:
        tools = await client.list_tools()

    assert {t.name for t in tools.tools} == {
        "list_documents",
        "extract_document",
        "get_extraction",
        "list_low_confidence_fields",
    }


async def test_extract_then_review_flow():
    async with Client(mcp) as client:
        extracted = payload(await client.call_tool("extract_document", {"document_name": "coi_002_messy.txt"}))
        assert extracted["status"] == "needs_review"

        review = payload(
            await client.call_tool("list_low_confidence_fields", {"document_id": extracted["document_id"]})
        )
        assert "certificate_holder" in {f["name"] for f in review["fields"]}

        stored = payload(await client.call_tool("get_extraction", {"document_id": extracted["document_id"]}))
        assert stored["document_name"] == "coi_002_messy.txt"


@pytest.mark.parametrize(
    "name",
    ["../pyproject.toml", "/etc/passwd", "..%2Fsecrets.txt", "missing.txt", "coi_001.txt; rm -rf /"],
)
async def test_extract_rejects_paths_and_unknown_documents(name):
    async with Client(mcp) as client:
        result = await client.call_tool("extract_document", {"document_name": name})
    assert result.is_error


async def test_get_extraction_rejects_malformed_ids():
    async with Client(mcp) as client:
        result = await client.call_tool("get_extraction", {"document_id": "../../etc/passwd"})
    assert result.is_error


async def test_every_call_is_audited(isolated_environment):
    async with Client(mcp) as client:
        await client.call_tool("extract_document", {"document_name": "coi_001.txt"})
        await client.call_tool("extract_document", {"document_name": "../nope.txt"})

    lines = (isolated_environment / "audit.jsonl").read_text().splitlines()
    records = [json.loads(line) for line in lines]
    assert [r["outcome"] for r in records] == ["ok", "error"]
    assert records[0]["tool"] == "extract_document"
    assert records[0]["arguments"] == {"document_name": "coi_001.txt"}


@pytest.mark.parametrize(
    ("tool", "arguments", "expected"),
    [
        ("extract_document", {"document_name": "missing.txt"}, "Unknown document: missing.txt"),
        ("extract_document", {"document_name": "../pyproject.toml"}, "plain .txt file name"),
        ("get_extraction", {"document_id": "doc_000000000000"}, "No extraction found for doc_000000000000"),
        ("list_low_confidence_fields", {"document_id": "doc_000000000000"}, "No extraction found"),
        ("get_extraction", {"document_id": "../../etc/passwd"}, "doc_ followed by 12 hex characters"),
    ],
)
async def test_tool_errors_tell_the_agent_what_went_wrong(tool, arguments, expected):
    async with Client(mcp) as client:
        result = await client.call_tool(tool, arguments)
    assert result.is_error
    assert expected in result.content[0].text


async def test_invalid_id_is_not_echoed_back(isolated_environment):
    long_id = "A" * 5000
    async with Client(mcp) as client:
        result = await client.call_tool("get_extraction", {"document_id": long_id})
    assert result.is_error
    assert long_id not in result.content[0].text


async def test_document_that_is_not_utf8_gets_a_plain_message(isolated_environment, monkeypatch):
    inbox = isolated_environment / "inbox"
    inbox.mkdir()
    (inbox / "latin1.txt").write_bytes("Insured: Caf\xe9 Freight\n".encode("latin-1"))
    monkeypatch.setenv("DOCINTEL_INBOX", str(inbox))
    async with Client(mcp) as client:
        result = await client.call_tool("extract_document", {"document_name": "latin1.txt"})
    assert result.is_error
    assert "not UTF-8 text" in result.content[0].text
    assert "codec" not in result.content[0].text


async def test_unexpected_errors_stay_on_the_server(isolated_environment):
    """A corrupted stored result is a crash: the agent must not see the stored values."""
    async with Client(mcp) as client:
        extracted = payload(await client.call_tool("extract_document", {"document_name": "coi_001.txt"}))
        stored = isolated_environment / "results" / f"{extracted['document_id']}.json"
        record = json.loads(stored.read_text())
        record["status"] = "SECRET-VALUE-FROM-DOCUMENT"
        stored.write_text(json.dumps(record))
        result = await client.call_tool("get_extraction", {"document_id": extracted["document_id"]})
    assert result.is_error
    assert "SECRET-VALUE-FROM-DOCUMENT" not in result.content[0].text
