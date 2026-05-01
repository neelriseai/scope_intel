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


class TestMemPalaceConfidenceDecay:
    """Phase 6.1 — non-destructive effective_confidence at fetch time."""

    def _backdate(self, repo, mem_id: str, days: int) -> None:
        """Rewrite ts on a memory entry to N days ago (for testing decay only)."""
        import datetime
        entries = store.read_mempalace(repo)
        new_ts = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
        new_ts_str = new_ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        for e in entries:
            if e.get("id") == mem_id:
                e["ts"] = new_ts_str
        # rewrite the JSONL
        path = store.mempalace_path(repo) if hasattr(store, "mempalace_path") else \
               (repo / ".scope-intelligence" / "mempalace.jsonl")
        path.write_text(
            "\n".join(json.dumps(e) for e in entries) + "\n",
            encoding="utf-8",
        )

    def test_effective_confidence_present_on_semantic(self, repo):
        add_memory(repo, "semantic", "fresh fact", confidence=0.9, features=["auth"])
        r = fetch_relevant(repo, feature="auth")
        sem = r["layers"]["semantic"]
        assert len(sem) >= 1
        assert "effective_confidence" in sem[0]

    def test_fresh_entry_effective_equals_base(self, repo):
        add_memory(repo, "semantic", "right now", confidence=0.8, features=["auth"])
        r = fetch_relevant(repo, feature="auth")
        sem = r["layers"]["semantic"][0]
        # Newly-added: age ~ 0, decay factor ~ 1.0
        assert abs(sem["effective_confidence"] - 0.8) < 0.01
        # Stored confidence is unchanged
        assert sem["confidence"] == 0.8

    def test_old_entry_effective_below_base(self, repo):
        e = add_memory(repo, "semantic", "ancient fact",
                       confidence=0.9, features=["auth"])
        # Push timestamp 180 days back — with default 90d half-life, factor = 0.25
        self._backdate(repo, e["id"], days=180)
        r = fetch_relevant(repo, feature="auth")
        sem = next(x for x in r["layers"]["semantic"] if x["id"] == e["id"])
        # Stored value is untouched...
        assert sem["confidence"] == 0.9
        # ...but effective is decayed
        assert sem["effective_confidence"] < 0.5
        assert sem["effective_confidence"] > 0.0

    def test_sort_order_uses_effective_confidence(self, repo):
        """A high base confidence that's decayed should rank below a fresh lower one."""
        old = add_memory(repo, "semantic", "old high",
                         confidence=0.95, features=["auth"])
        add_memory(repo, "semantic", "fresh moderate",
                   confidence=0.6, features=["auth"])
        # Decay the old one severely (5 half-lives back ~ 99% loss)
        self._backdate(repo, old["id"], days=450)
        r = fetch_relevant(repo, feature="auth")
        sem = r["layers"]["semantic"]
        notes = [s["note"] for s in sem]
        assert notes[0] == "fresh moderate", notes

    def test_per_entry_half_life_override(self, repo):
        """A short half-life makes the effective drop faster than the default."""
        e = add_memory(repo, "semantic", "expires fast",
                       confidence=0.9, features=["auth"], half_life_days=30)
        # 60 days = 2 half-lives → effective ~ 0.225
        self._backdate(repo, e["id"], days=60)
        r = fetch_relevant(repo, feature="auth")
        sem = next(x for x in r["layers"]["semantic"] if x["id"] == e["id"])
        assert sem["confidence"] == 0.9
        assert 0.15 < sem["effective_confidence"] < 0.30

    def test_config_half_life_used_when_no_override(self, repo):
        """Setting config.semantic_half_life affects every entry without an override."""
        cfg = store.read_json(repo, "config", store.default_config())
        cfg["semantic_half_life"] = 30  # aggressive decay repo-wide
        store.write_json(repo, "config", cfg)

        e = add_memory(repo, "semantic", "uses config decay",
                       confidence=0.9, features=["auth"])
        self._backdate(repo, e["id"], days=60)  # 2 half-lives at 30
        r = fetch_relevant(repo, feature="auth")
        sem = next(x for x in r["layers"]["semantic"] if x["id"] == e["id"])
        assert sem["effective_confidence"] < 0.30

    def test_entry_without_ts_keeps_base(self, repo):
        """Defensive: malformed entries shouldn't blow up fetch."""
        from scope_intel.core.mempalace import _effective_confidence
        eff = _effective_confidence({"confidence": 0.7, "ts": "not-a-date"})
        assert eff == 0.7


class TestMemTouch:
    """Phase 6.1 — scope mem touch reinforces a memory by resetting ts."""

    def _backdate(self, repo, mem_id: str, days: int) -> None:
        import datetime
        entries = store.read_mempalace(repo)
        new_ts = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
        new_ts_str = new_ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        for e in entries:
            if e.get("id") == mem_id:
                e["ts"] = new_ts_str
        path = repo / ".scope-intelligence" / "mempalace.jsonl"
        path.write_text(
            "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8"
        )

    def test_touch_updates_ts(self, repo):
        from scope_intel.core.mempalace import touch_memory
        import datetime
        e = add_memory(repo, "semantic", "aging fact", confidence=0.8, features=["auth"])
        self._backdate(repo, e["id"], days=100)

        result = touch_memory(repo, e["id"])
        assert "error" not in result, result
        # ts should be very recent (within last 5 seconds)
        ts = datetime.datetime.strptime(result["ts"], "%Y-%m-%dT%H:%M:%SZ")
        age = (datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - ts).total_seconds()
        assert age < 5

    def test_touch_records_old_ts_in_history(self, repo):
        from scope_intel.core.mempalace import touch_memory
        e = add_memory(repo, "semantic", "tracked fact", confidence=0.9, features=["auth"])
        self._backdate(repo, e["id"], days=50)
        # Read the backdated ts — that's what touch will move into history
        entries = store.read_mempalace(repo)
        backdated_ts = next(x["ts"] for x in entries if x["id"] == e["id"])

        result = touch_memory(repo, e["id"])
        assert "reinforced_at" in result
        # The backdated ts (the one that was live before touch) should be in history
        assert backdated_ts in result["reinforced_at"]

    def test_touch_accumulates_history(self, repo):
        from scope_intel.core.mempalace import touch_memory
        e = add_memory(repo, "semantic", "multi-touch", confidence=0.9, features=["auth"])
        touch_memory(repo, e["id"])
        result = touch_memory(repo, e["id"])
        assert len(result.get("reinforced_at", [])) >= 2

    def test_touch_raises_effective_confidence(self, repo):
        from scope_intel.core.mempalace import touch_memory
        from scope_intel.core.mempalace import _effective_confidence
        e = add_memory(repo, "semantic", "decayed", confidence=0.9, features=["auth"])
        self._backdate(repo, e["id"], days=270)  # 3 half-lives → ~0.11 effective
        # Verify it actually decayed
        entries = store.read_mempalace(repo)
        decayed_entry = next(x for x in entries if x["id"] == e["id"])
        eff_before = _effective_confidence(decayed_entry)
        assert eff_before < 0.2

        touch_memory(repo, e["id"])
        entries = store.read_mempalace(repo)
        fresh = next(x for x in entries if x["id"] == e["id"])
        eff_after = _effective_confidence(fresh)
        assert eff_after > eff_before

    def test_touch_unknown_id_returns_error(self, repo):
        from scope_intel.core.mempalace import touch_memory
        result = touch_memory(repo, "mp_nonexistent")
        assert "error" in result


class TestMemPrune:
    """Phase 6.1 — scope mem prune deletes semantics below effective threshold."""

    def _backdate(self, repo, mem_id: str, days: int) -> None:
        import datetime
        entries = store.read_mempalace(repo)
        new_ts = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
        for e in entries:
            if e.get("id") == mem_id:
                e["ts"] = new_ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        path = repo / ".scope-intelligence" / "mempalace.jsonl"
        path.write_text(
            "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8"
        )

    def test_prune_removes_decayed_entries(self, repo):
        from scope_intel.core.mempalace import prune_memories
        old = add_memory(repo, "semantic", "ancient", confidence=0.9, features=["auth"])
        add_memory(repo, "semantic", "fresh", confidence=0.9, features=["auth"])
        # age old one 5 half-lives → effective ≈ 0.028
        self._backdate(repo, old["id"], days=450)

        result = prune_memories(repo, below=0.05)
        assert "error" not in result, result
        assert result["pruned"] == 1
        assert result["removed"][0]["id"] == old["id"]
        remaining = store.read_mempalace(repo)
        ids = [e["id"] for e in remaining]
        assert old["id"] not in ids

    def test_dry_run_does_not_delete(self, repo):
        from scope_intel.core.mempalace import prune_memories
        old = add_memory(repo, "semantic", "would-be-pruned",
                         confidence=0.9, features=["auth"])
        self._backdate(repo, old["id"], days=450)

        result = prune_memories(repo, below=0.05, dry_run=True)
        assert result["dry_run"] is True
        assert result["pruned"] == 0          # nothing actually deleted
        assert len(result["removed"]) == 1    # preview shows it
        remaining = store.read_mempalace(repo)
        ids = [e["id"] for e in remaining]
        assert old["id"] in ids              # still there

    def test_non_semantic_never_pruned(self, repo):
        from scope_intel.core.mempalace import prune_memories
        bug = add_memory(repo, "bug", "old bug", features=["auth"])
        self._backdate(repo, bug["id"], days=999)

        result = prune_memories(repo, below=0.99)
        assert result["pruned"] == 0
        remaining_ids = [e["id"] for e in store.read_mempalace(repo)]
        assert bug["id"] in remaining_ids

    def test_prune_result_keys(self, repo):
        from scope_intel.core.mempalace import prune_memories
        add_memory(repo, "semantic", "some fact", confidence=0.9, features=["auth"])
        result = prune_memories(repo, below=0.0)  # threshold 0 = nothing pruned
        for key in ("pruned", "kept", "dry_run", "threshold", "removed"):
            assert key in result

    def test_half_life_override_affects_pruning(self, repo):
        """A shorter override half-life decays faster, pruning entries that default wouldn't."""
        from scope_intel.core.mempalace import prune_memories
        e = add_memory(repo, "semantic", "medium age",
                       confidence=0.9, features=["auth"])
        # 45 days back — with default 90d HL: eff ≈ 0.636 (safe)
        # with 10d HL: eff ≈ 0.9 * 0.5^(45/10) ≈ 0.019 (prunable)
        self._backdate(repo, e["id"], days=45)

        safe = prune_memories(repo, below=0.05)           # default HL=90
        assert safe["pruned"] == 0

        aggressive = prune_memories(repo, below=0.05, half_life_days=10)
        assert aggressive["pruned"] == 1


class TestMemCapture:
    """Phase 6.2 — agent-triggered signal-based captures."""

    def test_capture_valid_signal(self, repo):
        from scope_intel.core.mempalace import capture_memory
        result = capture_memory(repo, "repeated-error",
                                "TypeError in payment.py line 42")
        assert "error" not in result, result
        assert result["type"] == "failure"
        assert "signal:repeated-error" in result["tags"]
        assert "source:agent" in result["tags"]

    def test_capture_validated_claim_sets_confidence(self, repo):
        from scope_intel.core.mempalace import capture_memory
        result = capture_memory(repo, "validated-claim",
                                "JWT signing uses HS256 — confirmed by user")
        assert result["type"] == "semantic"
        assert result["confidence"] == 0.7

    def test_capture_confidence_capped_at_0_7(self, repo):
        """All agent captures must be capped so they never outrank human entries."""
        from scope_intel.core.mempalace import capture_memory, CAPTURE_SIGNALS
        for signal in CAPTURE_SIGNALS:
            result = capture_memory(repo, signal, f"evidence for {signal}")
            assert "error" not in result or result.get("rate_limited"), result
            conf = result.get("confidence", 0)  # only semantic has it
            if conf:
                assert conf <= 0.7, f"confidence > 0.7 for {signal}"

    def test_capture_unknown_signal_returns_error(self, repo):
        from scope_intel.core.mempalace import capture_memory
        result = capture_memory(repo, "made-up-signal", "some evidence")
        assert "error" in result

    def test_capture_dry_run_no_write(self, repo):
        from scope_intel.core.mempalace import capture_memory
        result = capture_memory(repo, "surprising-fix",
                                "fixed off-by-one in paginator", dry_run=True)
        assert result.get("dry_run") is True
        assert "would_capture" in result
        remaining = store.read_mempalace(repo)
        assert len(remaining) == 0  # nothing written

    def test_capture_scope_hints_stored(self, repo):
        from scope_intel.core.mempalace import capture_memory
        result = capture_memory(repo, "scope-mismatch",
                                "feature mismatch detected",
                                feature="billing", file="src/billing/payment.py")
        assert result["scope"]["features"] == ["billing"]
        assert result["scope"]["files"] == ["src/billing/payment.py"]

    def test_capture_rate_limit(self, repo):
        from scope_intel.core.mempalace import capture_memory, _CAPTURE_RATE_LIMIT
        # Fill up the rate limit
        for i in range(_CAPTURE_RATE_LIMIT):
            r = capture_memory(repo, "repeated-error", f"error #{i}")
            assert "error" not in r or r.get("rate_limited"), r
        # Next one should be rate-limited
        r = capture_memory(repo, "repeated-error", "over the limit")
        assert r.get("rate_limited") is True


class TestFederation:
    """Phase 6.3 — cross-repo memory federation."""

    @pytest.fixture()
    def clean_manifest(self, monkeypatch, tmp_path):
        """Redirect the federation manifest to a temp dir so tests don't pollute ~/.scope-intelligence."""
        from scope_intel.core import federation as fed_mod
        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        monkeypatch.setattr(
            fed_mod, "_federation_path",
            lambda: fake_home / ".scope-intelligence" / "federation.json",
        )
        # Ensure the dir exists
        (fake_home / ".scope-intelligence").mkdir(parents=True, exist_ok=True)
        return fake_home

    def test_add_repo(self, repo, clean_manifest):
        from scope_intel.core.federation import federation_add, federation_list
        result = federation_add(str(repo), alias="main-repo")
        assert "error" not in result, result
        assert result["ok"] is True
        manifest = federation_list()
        aliases = [r["alias"] for r in manifest["repos"]]
        assert "main-repo" in aliases

    def test_add_nonexistent_path_errors(self, clean_manifest):
        from scope_intel.core.federation import federation_add
        result = federation_add("/no/such/path", alias="ghost")
        assert "error" in result

    def test_duplicate_alias_different_path_errors(self, repo, tmp_path, clean_manifest):
        from scope_intel.core.federation import federation_add
        other = tmp_path / "other"
        other.mkdir()
        federation_add(str(repo), alias="shared")
        result = federation_add(str(other), alias="shared")
        assert "error" in result

    def test_remove_repo(self, repo, clean_manifest):
        from scope_intel.core.federation import federation_add, federation_remove, federation_list
        federation_add(str(repo), alias="to-remove")
        result = federation_remove("to-remove")
        assert "error" not in result
        manifest = federation_list()
        assert not any(r["alias"] == "to-remove" for r in manifest["repos"])

    def test_remove_also_clears_links(self, repo, tmp_path, clean_manifest):
        from scope_intel.core.federation import (
            federation_add, federation_link, federation_remove, federation_list
        )
        sat = tmp_path / "sat"
        sat.mkdir()
        federation_add(str(repo), alias="main")
        federation_add(str(sat),  alias="satellite")
        federation_link("main", "satellite")
        federation_remove("satellite")
        manifest = federation_list()
        assert not any(lk["to"] == "satellite" for lk in manifest["links"])

    def test_link_creates_entry(self, repo, tmp_path, clean_manifest):
        from scope_intel.core.federation import federation_add, federation_link, federation_list
        sat = tmp_path / "sat"
        sat.mkdir()
        federation_add(str(repo), alias="main")
        federation_add(str(sat),  alias="satellite")
        federation_link("main", "satellite", scope="semantic")
        manifest = federation_list()
        assert any(
            lk["from"] == "main" and lk["to"] == "satellite" and lk["scope"] == "semantic"
            for lk in manifest["links"]
        )

    def test_link_unknown_alias_errors(self, repo, clean_manifest):
        from scope_intel.core.federation import federation_add, federation_link
        federation_add(str(repo), alias="main")
        result = federation_link("main", "no-such-alias")
        assert "error" in result

    def test_federated_fetch_returns_remote_entries(self, repo, tmp_path, clean_manifest):
        from scope_intel.core.federation import (
            federation_add, federation_link, federated_fetch
        )
        from scope_intel.core.mempalace import add_memory

        # Set up a satellite repo with its own indexed store
        sat = tmp_path / "satellite"
        sat.mkdir()
        store.ensure_index_dir(sat)
        store.write_json(sat, "config", store.default_config())
        add_memory(sat, "semantic", "shared constraint: always validate",
                   confidence=0.9, features=["auth"])

        federation_add(str(repo), alias="main")
        federation_add(str(sat),  alias="satellite")
        federation_link("main", "satellite", scope="semantic")

        result = federated_fetch(repo)
        assert result["local_alias"] == "main"
        assert result["total_remote"] == 1
        entry = result["sources"][0]["entries"][0]
        assert entry["_federation_source"] == "satellite"
        assert entry["note"] == "shared constraint: always validate"

    def test_federated_fetch_scope_filter(self, repo, tmp_path, clean_manifest):
        from scope_intel.core.federation import (
            federation_add, federation_link, federated_fetch
        )
        from scope_intel.core.mempalace import add_memory

        sat = tmp_path / "satellite"
        sat.mkdir()
        store.ensure_index_dir(sat)
        store.write_json(sat, "config", store.default_config())
        add_memory(sat, "semantic", "semantic fact", confidence=0.8)
        add_memory(sat, "bug", "a bug", features=["auth"])

        federation_add(str(repo), alias="main")
        federation_add(str(sat),  alias="satellite")
        # Only pull semantic from satellite
        federation_link("main", "satellite", scope="semantic")

        result = federated_fetch(repo)
        types = [e["type"] for e in result["sources"][0]["entries"]]
        assert "semantic" in types
        assert "bug" not in types

    def test_unregistered_repo_returns_note(self, repo, clean_manifest):
        from scope_intel.core.federation import federated_fetch
        result = federated_fetch(repo)
        assert result["local_alias"] is None
        assert result["total_remote"] == 0


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


# ===========================================================================
# Phase 5 — Auto-capture, Decay, Search, Export/Import, Conflicts
# ===========================================================================

from scope_intel.core.mempalace import (
    auto_capture_from_git,
    decay_confidence,
    detect_conflicts,
    export_memories,
    import_memories,
    search_memories,
)


class TestAutoCapture:
    def test_auto_capture_no_git_returns_graceful(self, repo):
        r = auto_capture_from_git(repo, days=30)
        assert "error" in r or r.get("captured", 0) == 0

    def test_auto_capture_dry_run_flag(self, repo):
        r = auto_capture_from_git(repo, days=30, dry_run=True)
        # no git in tmp_path — returns error, otherwise dry_run=True
        assert "error" in r or r.get("dry_run") is True

    def test_auto_capture_not_indexed_returns_error(self, tmp_path):
        r = auto_capture_from_git(tmp_path, days=30)
        assert "error" in r

    def test_auto_capture_days_in_result(self, repo):
        r = auto_capture_from_git(repo, days=7)
        assert r.get("days_scanned") == 7 or "error" in r


class TestDecayConfidence:
    def test_decay_semantic_dry_run(self, repo):
        add_memory(repo, "semantic", "auth uses JWT signing",
                   files=["src/auth/login.py"], confidence=1.0)
        r = decay_confidence(repo, half_life_days=1, floor=0.05, dry_run=True)
        assert "updated" in r
        assert r.get("dry_run") is True
        assert isinstance(r["changes"], list)

    def test_decay_dry_run_does_not_write(self, repo):
        add_memory(repo, "semantic", "billing uses Stripe", confidence=1.0)
        before = store.read_mempalace(repo)
        decay_confidence(repo, half_life_days=1, floor=0.05, dry_run=True)
        after = store.read_mempalace(repo)
        assert len(before) == len(after)

    def test_decay_floor_respected(self, repo):
        add_memory(repo, "semantic", "old fact", confidence=1.0)
        r = decay_confidence(repo, half_life_days=1, floor=0.3)
        for change in r.get("changes", []):
            assert change["new_confidence"] >= 0.3

    def test_decay_non_semantic_untouched(self, repo):
        add_memory(repo, "bug", "some bug note")
        before_count = len(store.read_mempalace(repo))
        decay_confidence(repo, half_life_days=1, floor=0.1)
        after = store.read_mempalace(repo)
        assert len(after) == before_count

    def test_decay_not_indexed_returns_error(self, tmp_path):
        r = decay_confidence(tmp_path, half_life_days=90)
        assert "error" in r


class TestSearch:
    def test_search_finds_relevant_memory(self, repo):
        add_memory(repo, "semantic", "auth uses JWT HS256 signing",
                   files=["src/auth/login.py"], confidence=0.9)
        add_memory(repo, "bug", "charge had float rounding bug",
                   files=["src/billing/payment.py"])
        r = search_memories(repo, "JWT auth signing")
        assert r["total"] >= 1
        assert any("JWT" in res.get("note", "") for res in r["results"])

    def test_search_returns_results_structure(self, repo):
        add_memory(repo, "note", "deployment runs on Kubernetes")
        r = search_memories(repo, "Kubernetes deployment")
        assert "results" in r
        assert "query" in r
        assert isinstance(r["results"], list)

    def test_search_kind_filter(self, repo):
        add_memory(repo, "semantic", "auth is stateless", confidence=0.8)
        add_memory(repo, "bug", "auth had a stateless bug")
        r = search_memories(repo, "stateless", kind="semantic")
        assert all(e.get("type") == "semantic" for e in r["results"])

    def test_search_returns_score(self, repo):
        add_memory(repo, "note", "billing charges in USD currency")
        r = search_memories(repo, "billing USD")
        for res in r["results"]:
            assert "_score" in res

    def test_search_not_indexed_returns_error(self, tmp_path):
        r = search_memories(tmp_path, "anything")
        assert "error" in r

    def test_search_limit_respected(self, repo):
        for i in range(5):
            add_memory(repo, "note", f"shared keyword memory number {i}")
        r = search_memories(repo, "shared keyword memory", limit=2)
        assert len(r["results"]) <= 2


class TestExportImport:
    def test_export_creates_file(self, repo, tmp_path):
        add_memory(repo, "note", "some memory to export")
        out = tmp_path / "export.json"
        r = export_memories(repo, out)
        assert r["exported"] >= 1
        assert out.exists()

    def test_export_valid_json(self, repo, tmp_path):
        add_memory(repo, "semantic", "exportable fact", confidence=0.8)
        out = tmp_path / "export.json"
        export_memories(repo, out)
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["version"] == 1
        assert "entries" in payload
        assert len(payload["entries"]) >= 1

    def test_import_merges_new_entries(self, repo, tmp_path):
        repo2 = tmp_path / "repo2"
        repo2.mkdir()
        store.ensure_index_dir(repo2)
        store.write_json(repo2, "config", store.default_config())
        build_index(repo2)
        add_memory(repo, "note", "memory to migrate")
        out = tmp_path / "export.json"
        export_memories(repo, out)
        r = import_memories(repo2, out, merge=True)
        assert r["imported"] >= 1

    def test_import_skips_duplicates(self, repo, tmp_path):
        add_memory(repo, "note", "duplicate memory")
        out = tmp_path / "export.json"
        export_memories(repo, out)
        r = import_memories(repo, out, merge=True)
        assert r["skipped"] >= 1

    def test_import_replace_mode(self, repo, tmp_path):
        add_memory(repo, "note", "original memory")
        out = tmp_path / "export.json"
        export_memories(repo, out)
        add_memory(repo, "note", "extra memory added after export")
        r = import_memories(repo, out, merge=False)
        assert r.get("replaced") is True

    def test_import_missing_file_returns_error(self, repo, tmp_path):
        r = import_memories(repo, tmp_path / "nonexistent.json")
        assert "error" in r

    def test_export_not_indexed_returns_error(self, tmp_path):
        out = tmp_path / "out.json"
        r = export_memories(tmp_path, out)
        assert "error" in r


class TestConflictDetection:
    def test_no_conflicts_when_empty(self, repo):
        r = detect_conflicts(repo)
        assert r["conflicts"] == []
        assert r["total"] == 0

    def test_detects_jwt_vs_session_conflict(self, repo):
        add_memory(repo, "semantic", "auth uses JWT tokens", confidence=0.9,
                   files=["src/auth/login.py"])
        add_memory(repo, "semantic", "auth uses session cookies", confidence=0.8,
                   files=["src/auth/login.py"])
        r = detect_conflicts(repo)
        assert r["total"] >= 1

    def test_no_conflict_on_unrelated_memories(self, repo):
        add_memory(repo, "semantic", "auth uses JWT", confidence=0.9,
                   files=["src/auth/login.py"])
        add_memory(repo, "semantic", "billing uses Stripe", confidence=0.9,
                   files=["src/billing/payment.py"])
        r = detect_conflicts(repo)
        assert r["total"] == 0

    def test_conflict_result_has_suggestion(self, repo):
        add_memory(repo, "semantic", "uses Postgres", confidence=1.0,
                   files=["src/auth/login.py"])
        add_memory(repo, "semantic", "uses MySQL", confidence=1.0,
                   files=["src/auth/login.py"])
        r = detect_conflicts(repo)
        for c in r.get("conflicts", []):
            assert "suggestion" in c

    def test_not_indexed_returns_error(self, tmp_path):
        r = detect_conflicts(tmp_path)
        assert "error" in r
