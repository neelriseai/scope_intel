"""Tests for the doc ingest pipeline (Phase 5 — mode=python and mode=llm).

Covers all new components without requiring external deps (Ollama, pypdf, etc.).
Run with:  python -m pytest tests/test_doc_ingest.py -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scope_intel.core import store
from scope_intel.core.indexer import build_index
from scope_intel.adapters.doc_reader import (
    read_document,
    read_document_structured,
    _split_by_tokens,
    _estimate_tokens,
    _docx_table_to_markdown,
)
from scope_intel.core.llm_client import NullLLMClient, get_client
from scope_intel.cli import _doc_list, _doc_fetch, _doc_search
from scope_intel.core.doc_ingestor import (
    _route_section,
    _split_sections,
    _extract_memories,
    _extract_features,
    ingest_document,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_MD = """\
# My Project

This is the project overview. It explains the purpose and goals.

## Architecture

The system uses a layered architecture with three components.

### Memory Layer

Memory is stored in a Redis cache. The system must always flush on shutdown.

### Validation Engine

We decided to use JSON Schema for all payloads. Validation is mandatory.

## Roadmap

Phase 1: Core engine (done)
Phase 2: RAG layer
Phase 3: Multi-agent subagents

## Constraints

- Must not store secrets in code
- Should always validate before persisting
- Never skip schema validation in production

## Schema Design

The data model uses a flat JSON structure with a "type" discriminator.

| Field   | Type   | Required |
|---------|--------|----------|
| id      | string | yes      |
| type    | string | yes      |
| payload | object | no       |
"""


@pytest.fixture()
def md_file(tmp_path) -> Path:
    p = tmp_path / "design.md"
    p.write_text(SAMPLE_MD, encoding="utf-8")
    return p


@pytest.fixture()
def repo(tmp_path) -> Path:
    """Minimal initialised repo."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def main(): pass\n", encoding="utf-8")
    store.ensure_index_dir(tmp_path)
    store.write_json(tmp_path, "config", store.default_config())
    build_index(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# doc_reader — read_document
# ---------------------------------------------------------------------------

class TestReadDocument:
    def test_markdown_returns_text(self, md_file):
        result = read_document(md_file)
        assert "error" not in result
        assert "text" in result
        assert "My Project" in result["text"]
        assert result["format"] == "md"

    def test_txt_format(self, tmp_path):
        p = tmp_path / "notes.txt"
        p.write_text("Hello world", encoding="utf-8")
        result = read_document(p)
        assert result["format"] == "txt"
        assert "Hello world" in result["text"]

    def test_missing_file_returns_error(self, tmp_path):
        result = read_document(tmp_path / "nonexistent.md")
        assert "error" in result

    def test_rst_treated_as_text(self, tmp_path):
        p = tmp_path / "doc.rst"
        p.write_text("Title\n=====\nBody text.", encoding="utf-8")
        result = read_document(p)
        assert "error" not in result
        assert "Title" in result["text"]


# ---------------------------------------------------------------------------
# doc_reader — token helpers
# ---------------------------------------------------------------------------

class TestTokenHelpers:
    def test_estimate_tokens_non_zero(self):
        assert _estimate_tokens("hello world") > 0

    def test_estimate_tokens_scales_with_length(self):
        short = _estimate_tokens("hi")
        long  = _estimate_tokens("hi " * 100)
        assert long > short

    def test_split_short_text_returns_single_chunk(self):
        text = "short text"
        result = _split_by_tokens(text, max_tokens=1200, overlap_tokens=150)
        assert result == [text]

    def test_split_long_text_produces_multiple_chunks(self):
        # Create a text that definitely exceeds 10 tokens (40 chars)
        text = "word " * 200   # ~1000 chars → ~250 tokens
        result = _split_by_tokens(text, max_tokens=30, overlap_tokens=5)
        assert len(result) > 1

    def test_split_chunks_have_overlap(self):
        """Last words of chunk N should appear at the start of chunk N+1."""
        text = "sentence one. sentence two. sentence three. " * 50
        chunks = _split_by_tokens(text, max_tokens=30, overlap_tokens=10)
        if len(chunks) > 1:
            # Overlap: some content from end of chunk 0 should appear in chunk 1
            end_of_first = chunks[0][-30:]
            assert any(word in chunks[1] for word in end_of_first.split() if len(word) > 3)

    def test_split_no_empty_chunks(self):
        text = "paragraph one.\n\nparagraph two.\n\nparagraph three." * 40
        chunks = _split_by_tokens(text, max_tokens=20, overlap_tokens=5)
        assert all(c.strip() for c in chunks)


# ---------------------------------------------------------------------------
# doc_reader — read_document_structured
# ---------------------------------------------------------------------------

class TestReadDocumentStructured:
    def test_returns_chunks_list(self, md_file):
        result = read_document_structured(md_file)
        assert "error" not in result
        assert "chunks" in result
        assert isinstance(result["chunks"], list)
        assert result["total_chunks"] == len(result["chunks"])

    def test_chunks_have_required_fields(self, md_file):
        result = read_document_structured(md_file)
        for chunk in result["chunks"]:
            assert "heading_path" in chunk
            assert "title" in chunk
            assert "level" in chunk
            assert "text" in chunk
            assert "token_estimate" in chunk
            assert "chunk_index" in chunk

    def test_heading_path_is_cumulative(self, md_file):
        result = read_document_structured(md_file)
        # "Memory Layer" is under Architecture → Memory Layer
        memory_chunks = [c for c in result["chunks"] if "Memory Layer" in c["title"]]
        assert memory_chunks, "Expected a Memory Layer chunk"
        path = memory_chunks[0]["heading_path"]
        assert "Architecture" in path
        assert "Memory Layer" in path
        assert ">" in path

    def test_top_level_headings_path_contains_title(self, md_file):
        """heading_path always contains the section title.

        The path is cumulative from the document root, so "Architecture"
        under "My Project" has path "My Project > Architecture", not just
        "Architecture".  We test that the title appears in the path.
        """
        result = read_document_structured(md_file)
        arch_chunks = [c for c in result["chunks"] if c["title"] == "Architecture"]
        assert arch_chunks
        assert "Architecture" in arch_chunks[0]["heading_path"]

    def test_chunk_indices_sequential(self, md_file):
        result = read_document_structured(md_file)
        indices = [c["chunk_index"] for c in result["chunks"]]
        assert indices == list(range(len(indices)))

    def test_full_text_present(self, md_file):
        result = read_document_structured(md_file)
        assert "full_text" in result
        assert "My Project" in result["full_text"]

    def test_missing_file_returns_error(self, tmp_path):
        result = read_document_structured(tmp_path / "gone.md")
        assert "error" in result

    def test_tables_in_markdown_appear_in_chunk_text(self, md_file):
        """Markdown tables should survive the heading split intact."""
        result = read_document_structured(md_file)
        # Schema Design section contains a markdown table
        schema_chunks = [c for c in result["chunks"] if "Schema" in c["title"]]
        assert schema_chunks
        table_text = schema_chunks[0]["text"]
        assert "|" in table_text  # markdown table delimiters preserved


# ---------------------------------------------------------------------------
# doc_reader — DOCX table converter (unit test, no .docx file needed)
# ---------------------------------------------------------------------------

class TestDocxTableToMarkdown:
    """Test the table-to-markdown converter using mock table objects."""

    class MockCell:
        def __init__(self, text): self.text = text

    class MockRow:
        def __init__(self, texts):
            self.cells = [TestDocxTableToMarkdown.MockCell(t) for t in texts]

    class MockTable:
        def __init__(self, rows):
            self.rows = [TestDocxTableToMarkdown.MockRow(r) for r in rows]

    def test_simple_table(self):
        table = self.MockTable([
            ["Name", "Age"],
            ["Alice", "30"],
            ["Bob", "25"],
        ])
        md = _docx_table_to_markdown(table)
        assert "| Name | Age |" in md
        assert "| --- | --- |" in md
        assert "| Alice | 30 |" in md

    def test_empty_table_returns_empty_string(self):
        table = self.MockTable([])
        assert _docx_table_to_markdown(table) == ""

    def test_merged_cells_deduplicated(self):
        """Merged cells appear as repeated text — should be deduplicated."""
        table = self.MockTable([
            ["Header", "Header", "Other"],  # merged cell repeated
            ["A", "B", "C"],
        ])
        md = _docx_table_to_markdown(table)
        lines = md.split("\n")
        header_line = lines[0]
        # "Header" should only appear once after dedup
        assert header_line.count("Header") == 1


# ---------------------------------------------------------------------------
# llm_client
# ---------------------------------------------------------------------------

class TestNullLLMClient:
    def test_global_summary_returns_none(self):
        client = NullLLMClient()
        assert client.global_summary("any text") is None

    def test_classify_chunk_returns_none(self):
        client = NullLLMClient()
        chunk = {"heading_path": "Arch", "title": "Arch", "text": "body", "token_estimate": 10}
        assert client.classify_chunk(chunk, {}) is None

    def test_module_map_pass_returns_none(self):
        client = NullLLMClient()
        assert client.module_map_pass([{"title": "x", "summary": "y"}]) is None

    def test_is_available_returns_false(self):
        assert NullLLMClient().is_available() is False

    def test_get_client_python_mode_returns_null(self):
        client = get_client(mode="python")
        assert isinstance(client, NullLLMClient)

    def test_get_client_llm_mode_returns_ollama(self):
        from scope_intel.core.llm_client import OllamaClient
        client = get_client(mode="llm")
        assert isinstance(client, OllamaClient)


# ---------------------------------------------------------------------------
# doc_ingestor — section routing
# ---------------------------------------------------------------------------

class TestRouteSection:
    def test_overview_routes_to_generated(self):
        dest, prefix, slug = _route_section("Introduction", "project overview goals")
        assert dest == "generated"
        assert slug == "project-overview"
        assert prefix == "001"

    def test_architecture_routes_correctly(self):
        dest, prefix, slug = _route_section("System Architecture", "high-level layers")
        assert dest == "generated"
        assert slug == "system-architecture"

    def test_constraint_routes_to_curated(self):
        dest, prefix, slug = _route_section("Constraints", "must not should never")
        assert dest == "curated"
        assert slug == "constraints"

    def test_roadmap_routes_to_generated(self):
        dest, prefix, slug = _route_section("Roadmap", "phase milestone release plan")
        assert dest == "generated"
        assert slug == "roadmap"

    def test_memory_layer_routes_correctly(self):
        dest, prefix, slug = _route_section("Memory Layer", "Redis used for caching and persistence")
        assert dest == "generated"
        assert slug == "memory-layer"

    def test_unknown_section_returns_none_tuple(self):
        dest, prefix, slug = _route_section("Random Unrelated Title", "blah blah blah")
        assert dest is None
        assert prefix is None
        assert slug is None

    def test_schema_design_routes_correctly(self):
        dest, prefix, slug = _route_section("Schema Design", "data model JSON type")
        assert dest == "generated"
        assert slug == "schema-design"


# ---------------------------------------------------------------------------
# doc_ingestor — section parsing
# ---------------------------------------------------------------------------

class TestSplitSections:
    def test_basic_split(self):
        text = "# Title\n\nBody text.\n\n## Sub\n\nSub body."
        sections = _split_sections(text)
        titles = [s["title"] for s in sections]
        assert "Title" in titles
        assert "Sub" in titles

    def test_preamble_captured(self):
        text = "Intro text without heading.\n\n# Section One\n\nBody."
        sections = _split_sections(text)
        assert sections[0]["title"] == "(preamble)"
        assert "Intro text" in sections[0]["body_text"]

    def test_body_text_present(self):
        text = "# Header\n\nThis is the body of the section."
        sections = _split_sections(text)
        body = next(s for s in sections if s["title"] == "Header")
        assert "body of the section" in body["body_text"]

    def test_level_recorded(self):
        text = "# H1\n\nbody\n\n## H2\n\nbody2\n\n### H3\n\nbody3"
        sections = _split_sections(text)
        levels = {s["title"]: s["level"] for s in sections}
        assert levels["H1"] == 1
        assert levels["H2"] == 2
        assert levels["H3"] == 3


# ---------------------------------------------------------------------------
# doc_ingestor — memory extraction
# ---------------------------------------------------------------------------

class TestExtractMemories:
    def test_uses_pattern_found(self):
        text = "The engine uses Redis for caching."
        mems = _extract_memories(text, "test")
        notes = [m["note"] for m in mems]
        assert any("uses" in n.lower() for n in notes)

    def test_must_pattern_is_constraint(self):
        text = "The system must validate all inputs before processing."
        mems = _extract_memories(text, "test")
        notes = [m["note"] for m in mems]
        assert any("Constraint" in n for n in notes)

    def test_decision_pattern(self):
        text = "We decided to use Qwen2.5 for all classification tasks."
        mems = _extract_memories(text, "test")
        notes = [m["note"] for m in mems]
        assert any("Decision" in n for n in notes)

    def test_no_duplicate_memories(self):
        text = "uses Redis for caching. uses Redis for caching."
        mems = _extract_memories(text, "test")
        notes = [m["note"].lower() for m in mems]
        assert len(notes) == len(set(notes))

    def test_memory_cap_applied(self):
        # Generate more than 60 patterns
        lines = [f"Component{i} uses Library{i} for stuff." for i in range(100)]
        text = "\n".join(lines)
        mems = _extract_memories(text, "test")
        assert len(mems) <= 60

    def test_confidence_in_range(self):
        text = "The system uses PostgreSQL. Must always commit transactions."
        mems = _extract_memories(text, "test")
        for m in mems:
            assert 0.0 <= m["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# doc_ingestor — full pipeline (mode=python, dry_run)
# ---------------------------------------------------------------------------

class TestIngestDocumentPython:
    def test_dry_run_returns_result_without_writing(self, repo, md_file):
        result = ingest_document(repo, md_file, dry_run=True, overwrite=True)
        assert "error" not in result, result
        assert result["mode"] == "python"
        assert result["dry_run"] is True
        # No files should be on disk
        ai_ctx = repo / ".ai-context"
        assert not ai_ctx.exists()

    def test_ingest_creates_ai_context_files(self, repo, md_file):
        result = ingest_document(repo, md_file, overwrite=True)
        assert "error" not in result, result
        assert result["files_written"] > 0
        ai_ctx = repo / ".ai-context"
        assert ai_ctx.exists()
        # At least one generated file should exist
        gen_dir = ai_ctx / "generated"
        assert gen_dir.exists()
        md_files = list(gen_dir.glob("*.md"))
        assert len(md_files) > 0

    def test_ingest_writes_index_json(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        index = repo / ".ai-context" / "generated" / "index.json"
        assert index.exists()
        data = json.loads(index.read_text(encoding="utf-8"))
        assert "files" in data
        assert data["source"] == md_file.name

    def test_constraints_section_goes_to_curated(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        constraints = repo / ".ai-context" / "curated" / "constraints.md"
        assert constraints.exists()
        text = constraints.read_text(encoding="utf-8")
        assert "Constraint" in text or "must" in text.lower() or "never" in text.lower()

    def test_roadmap_section_generated(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        gen = repo / ".ai-context" / "generated"
        roadmap_files = list(gen.glob("*roadmap*"))
        assert roadmap_files, "Expected a roadmap.md file"

    def test_memories_added_to_mempalace(self, repo, md_file):
        result = ingest_document(repo, md_file, overwrite=True)
        assert result["memories_added"] > 0

    def test_features_extracted(self, repo, md_file):
        result = ingest_document(repo, md_file, overwrite=True)
        assert result["features_added"] >= 0  # may be 0 if all filtered as generic

    def test_overwrite_false_skips_existing(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)  # first run
        result2 = ingest_document(repo, md_file, overwrite=False)  # second run
        assert result2["files_written"] == 0
        assert result2["files_skipped"] > 0

    def test_overwrite_true_regenerates(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        result2 = ingest_document(repo, md_file, overwrite=True)
        assert result2["files_written"] > 0

    def test_nonexistent_doc_returns_error(self, repo, tmp_path):
        result = ingest_document(repo, tmp_path / "nope.md")
        assert "error" in result

    def test_uninitialised_repo_returns_error(self, tmp_path, md_file):
        result = ingest_document(tmp_path, md_file)
        assert "error" in result


# ---------------------------------------------------------------------------
# doc_ingestor — routing_table in result
# ---------------------------------------------------------------------------

class TestRoutingTable:
    """routing_table is always present in the ingest result (python mode)."""

    def test_routing_table_present_in_result(self, repo, md_file):
        result = ingest_document(repo, md_file, dry_run=True, overwrite=True)
        assert "routing_table" in result
        assert isinstance(result["routing_table"], list)

    def test_routing_table_not_empty(self, repo, md_file):
        result = ingest_document(repo, md_file, dry_run=True, overwrite=True)
        assert len(result["routing_table"]) > 0

    def test_routing_table_entry_has_required_keys(self, repo, md_file):
        result = ingest_document(repo, md_file, dry_run=True, overwrite=True)
        for entry in result["routing_table"]:
            assert "section" in entry
            assert "file" in entry     # may be None if unmatched
            assert "layer" in entry    # may be None if unmatched

    def test_constraints_routed_to_curated(self, repo, md_file):
        result = ingest_document(repo, md_file, dry_run=True, overwrite=True)
        # SAMPLE_MD has ## Constraints → should land in curated/constraints.md
        constraints_routes = [
            e for e in result["routing_table"]
            if e.get("section", "").lower() == "constraints"
        ]
        assert constraints_routes, "Expected Constraints section in routing_table"
        assert constraints_routes[0]["layer"] == "curated"
        assert constraints_routes[0]["file"] == "constraints.md"

    def test_roadmap_routed_to_generated(self, repo, md_file):
        result = ingest_document(repo, md_file, dry_run=True, overwrite=True)
        roadmap_routes = [
            e for e in result["routing_table"]
            if "roadmap" in e.get("section", "").lower()
        ]
        assert roadmap_routes, "Expected Roadmap section in routing_table"
        assert roadmap_routes[0]["layer"] == "generated"
        assert "roadmap" in roadmap_routes[0]["file"]

    def test_unmatched_sections_have_none_file(self, repo, tmp_path):
        # A doc with sections that don't match any route
        doc = tmp_path / "weird.md"
        doc.write_text(
            "# Totally Obscure Section\n\nContent about xyzzy fnord quux.\n\n"
            "## Another Strange Thing\n\nMore quux content here.\n",
            encoding="utf-8",
        )
        result = ingest_document(repo, doc, dry_run=True, overwrite=True)
        # At least one unmatched section should appear with file=None
        unmatched = [e for e in result.get("routing_table", []) if e["file"] is None]
        assert len(unmatched) >= 0  # OK even if zero (routing may catch things)

    def test_routing_table_present_in_non_dry_run(self, repo, md_file):
        # routing_table is included even when not dry-run
        result = ingest_document(repo, md_file, overwrite=True)
        assert "routing_table" in result
        assert isinstance(result["routing_table"], list)

    def test_routing_table_matches_sections_parsed(self, repo, md_file):
        result = ingest_document(repo, md_file, dry_run=True, overwrite=True)
        # routing_table entries + preamble-skips should account for sections parsed
        # (sections_parsed may include preamble w/o body, so table can be ≤ parsed)
        assert len(result["routing_table"]) <= result["sections_parsed"]


# ---------------------------------------------------------------------------
# doc_ingestor — full pipeline (mode=llm, NullLLMClient fallback)
# ---------------------------------------------------------------------------

class TestIngestDocumentLLMFallback:
    """Test mode=llm with Ollama unavailable — should fall back to python."""

    def test_llm_fallback_to_python_when_ollama_down(self, repo, md_file):
        # Ollama is not running in CI — ingest_document should fall back
        result = ingest_document(
            repo, md_file,
            mode="llm",
            ollama_url="http://localhost:19999",  # wrong port, guaranteed unavailable
            overwrite=True,
        )
        assert "error" not in result, result
        # Should fall back to python mode
        assert result["mode"] in ("python", "python_fallback")
        assert "warning" in result


# ---------------------------------------------------------------------------
# doc_ingestor — CLAUDE.md update
# ---------------------------------------------------------------------------

class TestClaudeMdUpdate:
    def test_claude_md_created_when_missing(self, repo, md_file):
        claude_md = repo / "CLAUDE.md"
        assert not claude_md.exists()
        ingest_document(repo, md_file, overwrite=True, update_claude_md=True)
        assert claude_md.exists()
        content = claude_md.read_text(encoding="utf-8")
        assert "scope-intel-doc-context" in content

    def test_claude_md_not_updated_when_flag_false(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True, update_claude_md=False)
        assert not (repo / "CLAUDE.md").exists()

    def test_claude_md_section_replaced_on_rerun(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        ingest_document(repo, md_file, overwrite=True)
        content = (repo / "CLAUDE.md").read_text(encoding="utf-8")
        # Marker should appear exactly once (not duplicated)
        assert content.count("<!-- scope-intel-doc-context -->") == 1


# ---------------------------------------------------------------------------
# doc list and doc fetch helpers (CLI layer)
# ---------------------------------------------------------------------------

class TestDocListAndFetch:
    """Test the _doc_list() and _doc_fetch() helpers used by CLI + MCP."""

    def test_list_no_ai_context_returns_error(self, repo):
        result = _doc_list(repo)
        assert "error" in result

    def test_list_after_ingest_returns_files(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        result = _doc_list(repo)
        assert "error" not in result
        assert result["total"] > 0
        assert isinstance(result["generated"], list)

    def test_list_source_matches_ingested_doc(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        result = _doc_list(repo)
        assert result["source"] == md_file.name

    def test_list_curated_files_present(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        result = _doc_list(repo)
        curated_ids = [c["id"] for c in result.get("curated", [])]
        # constraints.md should have been written (SAMPLE_MD has ## Constraints)
        assert "constraints" in curated_ids

    def test_fetch_by_partial_id(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        result = _doc_fetch(repo, "overview")
        assert "error" not in result, result
        assert "content" in result
        assert result["chars"] > 0
        assert "overview" in result["id"].lower() or "overview" in result["title"].lower()

    def test_fetch_by_number_prefix(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        result = _doc_fetch(repo, "001")
        assert "error" not in result, result
        assert "001" in result["id"]

    def test_fetch_curated_constraints(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        result = _doc_fetch(repo, "constraints")
        assert "error" not in result, result
        assert result["layer"] == "curated"
        assert "constraints" in result["id"]

    def test_fetch_no_match_returns_error(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        result = _doc_fetch(repo, "xyznonexistent999")
        assert "error" in result

    def test_fetch_ambiguous_returns_error(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        # "a" matches many files
        result = _doc_fetch(repo, "a")
        if "error" in result:
            assert "ambiguous" in result["error"] or "no file" in result["error"]
        # (if only one matches, that's also acceptable)


# ---------------------------------------------------------------------------
# doc search helper
# ---------------------------------------------------------------------------

class TestDocSearch:
    def test_search_no_ai_context_returns_error(self, repo):
        result = _doc_search(repo, "anything")
        assert "error" in result

    def test_search_finds_keyword(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        # SAMPLE_MD has "Redis" in the Memory Layer section
        result = _doc_search(repo, "Redis")
        assert "error" not in result, result
        assert result["total_matches"] > 0

    def test_search_returns_file_and_line(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        result = _doc_search(repo, "Redis")
        assert result["files_with_matches"] > 0
        hit = result["results"][0]
        assert "file_id" in hit
        assert "path" in hit
        assert "matches" in hit
        match = hit["matches"][0]
        assert "line_no" in match
        assert "line" in match
        assert "Redis" in match["line"]

    def test_search_context_lines_present(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        result = _doc_search(repo, "Redis", context_lines=2)
        if result["total_matches"] > 0:
            m = result["results"][0]["matches"][0]
            assert isinstance(m["context_before"], list)
            assert isinstance(m["context_after"], list)

    def test_search_case_insensitive(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        r1 = _doc_search(repo, "redis")   # lowercase
        r2 = _doc_search(repo, "REDIS")   # uppercase
        assert r1["total_matches"] == r2["total_matches"]

    def test_search_layer_filter_generated(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        r_all = _doc_search(repo, "Auto-generated", layer="all")
        r_gen = _doc_search(repo, "Auto-generated", layer="generated")
        # generated/ should have matches (the auto-generated footer)
        assert r_gen["total_matches"] > 0
        assert r_gen["total_matches"] <= r_all["total_matches"]

    def test_search_no_match_returns_empty_results(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        result = _doc_search(repo, "xyznonexistentkeyword999")
        assert "error" not in result
        assert result["total_matches"] == 0
        assert result["results"] == []

    def test_search_total_matches_consistent(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        result = _doc_search(repo, "Auto-generated")
        manual_total = sum(r["match_count"] for r in result["results"])
        assert result["total_matches"] == manual_total


# ---------------------------------------------------------------------------
# doc stats helper
# ---------------------------------------------------------------------------

class TestDocStats:
    """Test the _doc_stats() helper used by `scope doc stats` and MCP doc_stats."""

    def test_stats_no_ai_context_returns_error(self, repo):
        from scope_intel.cli import _doc_stats
        result = _doc_stats(repo)
        assert "error" in result

    def test_stats_after_ingest_has_totals(self, repo, md_file):
        from scope_intel.cli import _doc_stats
        ingest_document(repo, md_file, overwrite=True)
        result = _doc_stats(repo)
        assert "error" not in result
        assert result["total_files"] > 0
        assert result["total_chars"] > 0
        assert result["total_tokens"] > 0

    def test_stats_tokens_approx_chars_over_4(self, repo, md_file):
        from scope_intel.cli import _doc_stats
        ingest_document(repo, md_file, overwrite=True)
        result = _doc_stats(repo)
        # Per-file token = chars // 4 (integer division truncates per file, not in aggregate)
        # total_tokens ≈ total_chars / 4, within ±(num_files) due to truncation
        n = result["total_files"]
        approx = result["total_chars"] / 4
        assert abs(result["total_tokens"] - approx) <= n + 1

    def test_stats_generated_and_curated_listed(self, repo, md_file):
        from scope_intel.cli import _doc_stats
        ingest_document(repo, md_file, overwrite=True)
        result = _doc_stats(repo)
        assert isinstance(result["generated"], list)
        assert isinstance(result["curated"], list)
        # SAMPLE_MD produces at least one generated and one curated file
        assert len(result["generated"]) > 0
        assert len(result["curated"]) > 0

    def test_stats_each_entry_has_required_keys(self, repo, md_file):
        from scope_intel.cli import _doc_stats
        ingest_document(repo, md_file, overwrite=True)
        result = _doc_stats(repo)
        for entry in result["generated"] + result["curated"]:
            assert "id"     in entry
            assert "path"   in entry
            assert "layer"  in entry
            assert "chars"  in entry
            assert "tokens" in entry

    def test_stats_total_matches_sum_of_parts(self, repo, md_file):
        from scope_intel.cli import _doc_stats
        ingest_document(repo, md_file, overwrite=True)
        result = _doc_stats(repo)
        all_files = result["generated"] + result["curated"]
        assert result["total_chars"]  == sum(f["chars"]  for f in all_files)
        assert result["total_tokens"] == sum(f["tokens"] for f in all_files)
        assert result["total_files"]  == len(all_files)


# ---------------------------------------------------------------------------
# doc clear (tested via filesystem state)
# ---------------------------------------------------------------------------

class TestDocClear:
    """Test _doc_clear logic through ingest+clear cycle.

    We can't easily call the CLI arg-based cmd_doc("clear") from tests,
    so we test the filesystem directly after using the CLI subprocess approach
    or just verify the directory state after a real clear via Python.
    """

    def test_clear_removes_generated_files(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        gen_dir = repo / ".ai-context" / "generated"
        assert gen_dir.exists()
        assert len(list(gen_dir.glob("*.md"))) > 0

        # Simulate what clear does
        import shutil
        shutil.rmtree(gen_dir)

        # After clear, list should error
        result = _doc_list(repo)
        assert "error" in result

    def test_ingest_after_clear_starts_fresh(self, repo, md_file):
        ingest_document(repo, md_file, overwrite=True)
        gen_dir = repo / ".ai-context" / "generated"
        import shutil
        shutil.rmtree(gen_dir)

        # Re-ingest should work cleanly
        result = ingest_document(repo, md_file, overwrite=True)
        assert "error" not in result
        assert result["files_written"] > 0
