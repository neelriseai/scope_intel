"""Unit test suite for scope-intelligence-toolkit.

Covers all phases without needing git or external deps.
Run with: python -m pytest tests/test_suite.py -v
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

# ensure the package is importable from this directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from scope_intel.core import store
from scope_intel.core.indexer import build_index
from scope_intel.core.mempalace import (
    add_memory,
    compute_churn,
    fetch_relevant,
    list_memories,
    resolve_memory,
    memory_stats,
)
from scope_intel.core.query_engine import (
    find_impacted_files,
    get_feature_scope,
    get_related_tests,
    get_repo_summary,
    get_symbol_context,
    get_touchpoints,
    get_callers,
    get_callees,
)
from scope_intel.core.tracker import compute_savings_summary, compute_global_summary, log_query
from scope_intel.core.reporter import format_terminal, format_html, format_global_terminal, format_global_html
from scope_intel.core.diff import compute_diff_scope


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def repo(tmp_path):
    """Minimal repo with auth + billing features."""
    (tmp_path / "src" / "auth").mkdir(parents=True)
    (tmp_path / "src" / "billing").mkdir(parents=True)
    (tmp_path / "tests").mkdir()

    (tmp_path / "src" / "auth" / "login.py").write_text(
        'import os\n'
        'SECRET = os.environ.get("SECRET", "dev")\n'
        'def login(user, pwd): return _token(user)\n'
        'def _token(user): return user + SECRET\n'
        'def validate(token): return len(token) > 0\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "billing" / "payment.py").write_text(
        'from src.auth.login import validate\n'
        'def charge(token, amount):\n'
        '    if not validate(token): raise ValueError("bad token")\n'
        '    return {"status": "ok", "amount": amount}\n',
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_auth.py").write_text(
        'import pytest\n'
        'from src.auth.login import login, validate\n'
        'def test_login(): assert login("a","b")\n'
        'def test_validate(): assert validate("tok")\n',
        encoding="utf-8",
    )

    store.ensure_index_dir(tmp_path)
    store.write_json(tmp_path, "config", store.default_config())
    build_index(tmp_path)
    return tmp_path


@pytest.fixture()
def empty_repo(tmp_path):
    store.ensure_index_dir(tmp_path)
    store.write_json(tmp_path, "config", store.default_config())
    return tmp_path


# ===========================================================================
# Phase 1+2 — Index + Query engine
# ===========================================================================

class TestIndex:
    def test_index_creates_files(self, repo):
        assert (repo / ".scope-intelligence" / "features.json").exists()
        assert (repo / ".scope-intelligence" / "symbols.json").exists()
        assert (repo / ".scope-intelligence" / "dependencies.json").exists()

    def test_features_detected(self, repo):
        data = store.read_json(repo, "features", {})
        ids = [f["id"] for f in data.get("features", [])]
        assert "auth" in ids
        assert "billing" in ids

    def test_symbols_indexed(self, repo):
        data = store.read_json(repo, "symbols", {})
        names = [s["name"] for s in data.get("symbols", [])]
        assert "login" in names
        assert "validate" in names

    def test_tests_linked(self, repo):
        data = store.read_json(repo, "tests", {})
        files = [t["file"] for t in data.get("tests", [])]
        assert any("test_auth" in f for f in files)

    def test_incremental_skips_unchanged(self, repo):
        result = build_index(repo, incremental=True)
        assert result.get("skipped_unchanged", 0) > 0

    def test_only_files_mode(self, repo):
        result = build_index(repo, only_files=["src/auth/login.py"])
        assert result["files"] >= 1


class TestQueryEngine:
    def test_repo_summary(self, repo):
        s = get_repo_summary(repo)
        assert s["totals"]["files"] >= 3
        assert s["totals"]["features"] >= 2
        assert "python" in s["languages"]

    def test_feature_scope_found(self, repo):
        r = get_feature_scope(repo, "auth")
        assert "error" not in r
        assert any("login.py" in f for f in r["files"])

    def test_feature_scope_alias(self, repo):
        r = get_feature_scope(repo, "billing")
        assert "error" not in r

    def test_feature_scope_missing(self, repo):
        r = get_feature_scope(repo, "nonexistent_xyz")
        assert "error" in r

    def test_find_impacted(self, repo):
        r = find_impacted_files(repo, file="src/auth/login.py")
        assert "error" not in r
        # billing imports auth — should appear in direct impact
        assert any("billing" in f or "payment" in f
                   for f in r.get("direct", []))

    def test_related_tests_by_file(self, repo):
        r = get_related_tests(repo, file="src/auth/login.py")
        assert any("test_auth" in m["file"] for m in r.get("matches", []))

    def test_related_tests_by_feature(self, repo):
        r = get_related_tests(repo, feature="auth")
        assert r.get("matches")

    def test_symbol_context_found(self, repo):
        r = get_symbol_context(repo, "validate")
        assert "error" not in r
        assert r["matches"]

    def test_symbol_context_missing(self, repo):
        r = get_symbol_context(repo, "totally_unknown_xyz")
        assert "error" in r

    def test_callers(self, repo):
        r = get_callers(repo, "validate")
        assert "error" not in r

    def test_callees(self, repo):
        r = get_callees(repo, "login")
        assert "error" not in r

    def test_touchpoints_configs(self, repo):
        r = get_touchpoints(repo, kind="configs")
        assert "error" not in r
        # SECRET env var should be indexed
        names = [c.get("name") for c in r.get("configs", [])]
        assert "SECRET" in names


# ===========================================================================
# Phase 3 — Tracker + Reporter
# ===========================================================================

class TestTracker:
    def test_log_query_writes_entry(self, repo):
        log_query(repo, "feature", {"name": "auth"}, ["src/auth/login.py"])
        entries = store.read_query_log(repo)
        assert len(entries) == 1
        assert entries[0]["cmd"] == "feature"

    def test_log_query_estimates_savings(self, repo):
        log_query(repo, "symbol", {"name": "validate"}, ["src/auth/login.py"])
        entries = store.read_query_log(repo)
        last = entries[-1]
        assert last["naive_tokens_est"] > last["scope_tokens_est"]
        assert last["tokens_saved_est"] >= 0

    def test_savings_summary_aggregates(self, repo):
        log_query(repo, "feature", {"name": "auth"}, ["src/auth/login.py"])
        log_query(repo, "feature", {"name": "billing"}, ["src/billing/payment.py"])
        s = compute_savings_summary(repo)
        assert s["total_queries"] >= 2
        assert s["total_tokens_saved_est"] >= 0
        assert "feature" in s["by_command"]

    def test_savings_summary_empty(self, empty_repo):
        s = compute_savings_summary(empty_repo)
        assert s["total_queries"] == 0
        assert "note" in s

    def test_global_summary_aggregates_two_repos(self, repo, empty_repo):
        log_query(repo, "feature", {"name": "auth"}, ["src/auth/login.py"])
        g = compute_global_summary([repo, empty_repo])
        assert g["totals"]["repos"] == 2
        assert g["totals"]["queries"] >= 1
        repo_names = [r["name"] for r in g["repos"]]
        assert repo.name in repo_names
        assert empty_repo.name in repo_names

    def test_global_summary_empty_repo_has_note(self, repo, empty_repo):
        g = compute_global_summary([repo, empty_repo])
        empty_entry = next(r for r in g["repos"] if r["name"] == empty_repo.name)
        assert "note" in empty_entry


class TestReporter:
    def test_format_terminal_no_data(self, empty_repo):
        s = compute_savings_summary(empty_repo)
        out = format_terminal(s)
        assert "No" in out or "no" in out

    def test_format_terminal_with_data(self, repo):
        log_query(repo, "feature", {"name": "auth"}, ["src/auth/login.py"])
        s = compute_savings_summary(repo)
        out = format_terminal(s)
        assert "TOKEN SAVINGS" in out
        assert "feature" in out

    def test_format_html_produces_valid_html(self, repo):
        log_query(repo, "symbol", {"name": "validate"}, ["src/auth/login.py"])
        s = compute_savings_summary(repo)
        h = format_html(s, repo)
        assert "<!DOCTYPE html>" in h
        assert "card-value" in h
        assert "bar-fill" in h

    def test_format_global_terminal(self, repo, empty_repo):
        log_query(repo, "feature", {"name": "auth"}, ["src/auth/login.py"])
        g = compute_global_summary([repo, empty_repo])
        out = format_global_terminal(g)
        assert "GLOBAL" in out
        assert repo.name in out

    def test_format_global_html(self, repo, empty_repo):
        log_query(repo, "feature", {"name": "auth"}, ["src/auth/login.py"])
        g = compute_global_summary([repo, empty_repo])
        h = format_global_html(g)
        assert "<!DOCTYPE html>" in h
        assert "Per-repo breakdown" in h
        assert repo.name in h
        assert empty_repo.name in h


# ===========================================================================
# Phase 3 — MCP server
# ===========================================================================

class TestMCPServer:
    def _send(self, server_module, msg: dict) -> dict:
        responses = []
        orig_write = __import__("sys").stdout.write

        captured = []

        def fake_write(s):
            captured.append(s)

        import scope_intel.mcp_server as mcp
        import io, sys as _sys
        old_stdout = _sys.stdout
        _sys.stdout = io.StringIO()
        mcp._send(msg)
        output = _sys.stdout.getvalue()
        _sys.stdout = old_stdout
        return json.loads(output.strip()) if output.strip() else {}

    def test_initialize(self, repo):
        import scope_intel.mcp_server as mcp
        import io, sys as _sys
        old = _sys.stdout
        _sys.stdout = io.StringIO()
        mcp._handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        out = _sys.stdout.getvalue()
        _sys.stdout = old
        r = json.loads(out)
        assert r["result"]["serverInfo"]["name"] == "scope-intelligence"

    def test_tools_list(self, repo):
        import scope_intel.mcp_server as mcp
        import io, sys as _sys
        old = _sys.stdout
        _sys.stdout = io.StringIO()
        mcp._handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        out = _sys.stdout.getvalue()
        _sys.stdout = old
        r = json.loads(out)
        names = [t["name"] for t in r["result"]["tools"]]
        assert "scope_summary" in names
        assert "mem_add" in names
        assert "mem_fetch" in names

    def test_unknown_method(self, repo):
        import scope_intel.mcp_server as mcp
        import io, sys as _sys
        old = _sys.stdout
        _sys.stdout = io.StringIO()
        mcp._handle({"jsonrpc": "2.0", "id": 3, "method": "bogus/method", "params": {}})
        out = _sys.stdout.getvalue()
        _sys.stdout = old
        r = json.loads(out)
        assert "error" in r

    def test_tools_call_scope_summary(self, repo):
        import scope_intel.mcp_server as mcp
        import io, sys as _sys
        old = _sys.stdout
        _sys.stdout = io.StringIO()
        mcp._handle({
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "scope_summary", "arguments": {"repo": str(repo)}}
        })
        out = _sys.stdout.getvalue()
        _sys.stdout = old
        r = json.loads(out)
        content = json.loads(r["result"]["content"][0]["text"])
        assert "totals" in content

    def test_notification_no_response(self, repo):
        import scope_intel.mcp_server as mcp
        import io, sys as _sys
        old = _sys.stdout
        _sys.stdout = io.StringIO()
        mcp._handle({"jsonrpc": "2.0", "method": "initialized", "params": {}})
        out = _sys.stdout.getvalue()
        _sys.stdout = old
        assert out.strip() == ""


# ===========================================================================
# Phase 4 — MemPalace
# ===========================================================================

class TestMemPalaceAdd:
    def test_add_episodic_bug(self, repo):
        e = add_memory(repo, "bug", "test bug", files=["src/auth/login.py"])
        assert e["type"] == "bug"
        assert e["id"].startswith("mp_")
        assert not e["resolved"]

    def test_add_semantic_with_confidence(self, repo):
        e = add_memory(repo, "semantic", "auth uses HS256", confidence=0.9,
                       features=["auth"])
        assert e["type"] == "semantic"
        assert e["confidence"] == 0.9

    def test_add_procedure_with_steps(self, repo):
        e = add_memory(repo, "procedure", "How to add endpoint",
                       steps=["Step 1", "Step 2"], features=["auth"])
        assert e["type"] == "procedure"
        assert e["steps"] == ["Step 1", "Step 2"]

    def test_add_procedure_requires_steps(self, repo):
        r = add_memory(repo, "procedure", "missing steps")
        assert "error" in r

    def test_add_invalid_type(self, repo):
        r = add_memory(repo, "garbage_type", "note")
        assert "error" in r

    def test_add_confidence_out_of_range(self, repo):
        r = add_memory(repo, "semantic", "bad conf", confidence=1.5)
        assert "error" in r

    def test_add_persists_to_jsonl(self, repo):
        add_memory(repo, "bug", "persisted bug", files=["src/auth/login.py"])
        entries = store.read_mempalace(repo)
        assert any(e["note"] == "persisted bug" for e in entries)


class TestMemPalaceFetch:
    def _seed(self, repo):
        add_memory(repo, "semantic", "auth fact", confidence=0.95, features=["auth"])
        add_memory(repo, "semantic", "billing fact", confidence=0.7, features=["billing"])
        add_memory(repo, "procedure", "workflow", steps=["s1", "s2"], features=["auth"])
        add_memory(repo, "bug", "auth bug", files=["src/auth/login.py"])
        add_memory(repo, "failure", "billing fail", features=["billing"])

    def test_fetch_by_feature_returns_layers(self, repo):
        self._seed(repo)
        r = fetch_relevant(repo, feature="auth")
        assert "error" not in r
        layers = r["layers"]
        assert "structural" in layers
        assert "semantic" in layers
        assert "procedural" in layers
        assert "episodic" in layers

    def test_semantic_sorted_by_confidence(self, repo):
        add_memory(repo, "semantic", "low conf", confidence=0.5, features=["auth"])
        add_memory(repo, "semantic", "high conf", confidence=0.99, features=["auth"])
        r = fetch_relevant(repo, feature="auth")
        sem = r["layers"]["semantic"]
        confs = [e["confidence"] for e in sem]
        assert confs == sorted(confs, reverse=True)

    def test_episodic_sorted_newest_first(self, repo):
        add_memory(repo, "bug", "old bug", features=["auth"])
        add_memory(repo, "bug", "new bug", features=["auth"])
        r = fetch_relevant(repo, feature="auth")
        epi = r["layers"]["episodic"]
        ts_list = [e["ts"] for e in epi]
        assert ts_list == sorted(ts_list, reverse=True)

    def test_structural_layer_populated(self, repo):
        r = fetch_relevant(repo, feature="auth")
        struct = r["layers"]["structural"]
        assert struct.get("features") or struct.get("files")

    def test_fetch_by_file_expands_neighbours(self, repo):
        add_memory(repo, "bug", "billing bug", files=["src/billing/payment.py"])
        # billing imports auth — fetching auth file should NOT reach billing memory
        # unless impacted expansion includes billing
        r = fetch_relevant(repo, file="src/auth/login.py")
        assert "error" not in r
        assert "layers" in r

    def test_fetch_by_symbol_uses_call_graph(self, repo):
        add_memory(repo, "bug", "validate bug", files=["src/auth/login.py"])
        r = fetch_relevant(repo, symbol="validate")
        assert "error" not in r
        # validate is in auth — its memory should surface
        all_episodic = r["layers"]["episodic"]
        notes = [e["note"] for e in all_episodic]
        assert any("validate" in n for n in notes)

    def test_fetch_excludes_resolved_by_default(self, repo):
        e = add_memory(repo, "bug", "resolved bug", features=["auth"], resolved=True)
        r = fetch_relevant(repo, feature="auth")
        ids = [x["id"] for x in r["layers"]["episodic"]]
        assert e["id"] not in ids

    def test_fetch_includes_resolved_when_flag_set(self, repo):
        e = add_memory(repo, "bug", "resolved bug", features=["auth"], resolved=True)
        r = fetch_relevant(repo, feature="auth", include_resolved=True)
        ids = [x["id"] for x in r["layers"]["episodic"]]
        assert e["id"] in ids

    def test_fetch_logs_to_query_log(self, repo):
        add_memory(repo, "bug", "some bug", features=["auth"])
        before = len(store.read_query_log(repo))
        fetch_relevant(repo, feature="auth")
        after = len(store.read_query_log(repo))
        assert after == before + 1

    def test_fetch_no_filter_returns_all(self, repo):
        add_memory(repo, "bug", "bug1", features=["auth"])
        add_memory(repo, "semantic", "fact1", confidence=0.8, features=["billing"])
        r = fetch_relevant(repo)
        total = r["total"]
        assert total >= 2


class TestMemPalaceList:
    def test_list_all(self, repo):
        add_memory(repo, "bug", "b1", features=["auth"])
        add_memory(repo, "semantic", "s1", confidence=0.9, features=["auth"])
        r = list_memories(repo)
        assert r["total"] >= 2

    def test_list_filter_by_type(self, repo):
        add_memory(repo, "bug", "b1", features=["auth"])
        add_memory(repo, "decision", "d1", features=["auth"])
        r = list_memories(repo, kind="bug")
        assert all(e["type"] == "bug" for e in r["entries"])

    def test_list_filter_by_tag(self, repo):
        add_memory(repo, "bug", "tagged", features=["auth"], tags=["jwt"])
        add_memory(repo, "bug", "untagged", features=["auth"])
        r = list_memories(repo, tag="jwt")
        assert all("jwt" in e.get("tags", []) for e in r["entries"])

    def test_list_open_only(self, repo):
        add_memory(repo, "bug", "open", features=["auth"])
        add_memory(repo, "bug", "resolved", features=["auth"], resolved=True)
        r = list_memories(repo, include_resolved=False)
        assert all(not e.get("resolved") for e in r["entries"])


class TestMemPalaceResolve:
    def test_resolve_marks_entry(self, repo):
        e = add_memory(repo, "bug", "fixable bug", features=["auth"])
        result = resolve_memory(repo, e["id"])
        assert result == {"resolved": e["id"]}
        entries = store.read_mempalace(repo)
        found = next(x for x in entries if x["id"] == e["id"])
        assert found["resolved"] is True
        assert "resolved_at" in found

    def test_resolve_unknown_id(self, repo):
        r = resolve_memory(repo, "mp_doesnotexist")
        assert "error" in r

    def test_resolve_does_not_corrupt_other_entries(self, repo):
        e1 = add_memory(repo, "bug", "bug1", features=["auth"])
        e2 = add_memory(repo, "bug", "bug2", features=["auth"])
        resolve_memory(repo, e1["id"])
        entries = store.read_mempalace(repo)
        e2_reloaded = next(x for x in entries if x["id"] == e2["id"])
        assert not e2_reloaded.get("resolved")


class TestMemPalaceStats:
    def test_stats_empty(self, empty_repo):
        s = memory_stats(empty_repo)
        assert s["total"] == 0

    def test_stats_counts_types(self, repo):
        add_memory(repo, "bug", "b", features=["auth"])
        add_memory(repo, "semantic", "s", confidence=0.9, features=["auth"])
        add_memory(repo, "procedure", "p", steps=["x"], features=["auth"])
        s = memory_stats(repo)
        assert s["total"] >= 3
        assert s["by_type"].get("bug", 0) >= 1
        assert s["by_type"].get("semantic", 0) >= 1

    def test_stats_open_vs_resolved(self, repo):
        add_memory(repo, "bug", "open", features=["auth"])
        e = add_memory(repo, "bug", "to resolve", features=["auth"])
        resolve_memory(repo, e["id"])
        s = memory_stats(repo)
        assert s["open"] >= 1
        assert s["resolved"] >= 1


class TestChurn:
    def test_churn_no_git(self, repo):
        # repo is a tmp_path with no git — should return error gracefully
        r = compute_churn(repo)
        assert "error" in r or "note" in r


# ===========================================================================
# Phase 4 — Diff (graceful without git)
# ===========================================================================

class TestDiff:
    def test_diff_no_git_graceful(self, repo):
        r = compute_diff_scope(repo, "HEAD~1")
        assert "error" in r


# ===========================================================================
# Store helpers
# ===========================================================================

class TestStore:
    def test_read_write_json(self, tmp_path):
        store.ensure_index_dir(tmp_path)
        store.write_json(tmp_path, "config", {"version": "1.0"})
        data = store.read_json(tmp_path, "config")
        assert data["version"] == "1.0"

    def test_read_missing_returns_default(self, tmp_path):
        store.ensure_index_dir(tmp_path)
        data = store.read_json(tmp_path, "config", {"fallback": True})
        assert data == {"fallback": True}

    def test_append_and_read_query_log(self, tmp_path):
        store.ensure_index_dir(tmp_path)
        store.append_query_log(tmp_path, {"cmd": "test", "ts": "2026-01-01T00:00:00Z"})
        store.append_query_log(tmp_path, {"cmd": "test2", "ts": "2026-01-02T00:00:00Z"})
        entries = store.read_query_log(tmp_path)
        assert len(entries) == 2
        assert entries[0]["cmd"] == "test"

    def test_append_and_read_mempalace(self, tmp_path):
        store.ensure_index_dir(tmp_path)
        store.append_mempalace(tmp_path, {"id": "mp_test", "type": "bug"})
        entries = store.read_mempalace(tmp_path)
        assert entries[0]["id"] == "mp_test"

    def test_is_initialized(self, tmp_path):
        assert not store.is_initialized(tmp_path)
        store.ensure_index_dir(tmp_path)
        assert store.is_initialized(tmp_path)
