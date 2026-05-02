"""Generate terminal and HTML token-savings reports from query_log.jsonl."""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Terminal report
# ---------------------------------------------------------------------------

def format_terminal(summary: dict) -> str:
    lines: list = []
    a = lines.append

    if summary.get("total_queries", 0) == 0:
        return summary.get("note", "No data.")

    a("=" * 60)
    a("  SCOPE INTELLIGENCE - TOKEN SAVINGS REPORT")
    a("=" * 60)
    a(f"  Total scope queries   : {summary['total_queries']}")
    a(f"  Tokens saved (est.)   : {summary['total_tokens_saved_est']:,}")
    a(f"  Naive cost (est.)     : {summary['total_naive_tokens_est']:,}")
    a(f"  Scope cost (est.)     : {summary['total_scope_tokens_est']:,}")
    a(f"  Savings               : {summary['savings_percent']}%")
    a("  Expected range        : 65-75% scope-only; up to 80-85% with inventory + memory/docs + compact sidecars")
    a(f"  Files avoided         : {summary['total_files_avoided']:,}  ({summary['total_loc_avoided']:,} LOC)")
    a(f"  Avg query latency     : {summary['avg_latency_ms']} ms")
    a("")
    a("  By command:")
    for cmd, stats in summary.get("by_command", {}).items():
        bar = "#" * min(int(stats["queries"] * 2), 30)
        a(f"    {cmd:<18} {stats['queries']:>4} queries   "
          f"~{stats['tokens_saved']:>7,} tkn saved   {bar}")
    a("")
    a("  By saving strategy:")
    for strategy, stats in summary.get("by_strategy", {}).items():
        bar = "#" * min(int(stats["queries"] * 2), 30)
        a(f"    {_strategy_label(strategy):<24} {stats['queries']:>4} queries   "
          f"~{stats['tokens_saved']:>7,} tkn saved   {bar}")

    compact = summary.get("compact_sidecars", {})
    a("")
    if compact.get("total", 0):
        a("  Compact sidecars:")
        a(f"    Files                 : {compact.get('total', 0):,}")
        a(f"    Source tokens (est.)  : {compact.get('source_tokens_est', 0):,}")
        a(f"    DSL tokens (est.)     : {compact.get('dsl_tokens_est', 0):,}")
        a(f"    Compact saving        : {compact.get('saving_percent_est', 0)}%")
    else:
        a("  Compact sidecars       : none built yet "
          "(run `scope compact build --target all`)")
    a("")
    a("  Strategy catalog (typical per-use savings):")
    for item in _STRATEGY_CATALOG:
        a(f"    {_strategy_label(item['strategy']):<24} {item['typical']:<28} {item['usage']}")
    a("")
    a("  Recent queries (newest first):")
    a(f"  {'Timestamp':<22} {'Command':<16} {'Files':<8} {'Saved(tkn)':<12} {'ms'}")
    a("  " + "-" * 70)
    for q in summary.get("recent_queries", [])[:15]:
        a(f"  {q.get('ts',''):<22} {q.get('cmd',''):<16} "
          f"{q.get('result_files', 0):<8} {q.get('tokens_saved_est', 0):<12,} "
          f"{q.get('latency_ms', 0)}")
    a("=" * 60)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1117;
       color: #e2e8f0; padding: 2rem; }
h1 { font-size: 1.5rem; font-weight: 700; color: #7dd3fc; margin-bottom: 0.25rem; }
.sub { font-size: 0.8rem; color: #64748b; margin-bottom: 2rem; }
.cards { display: flex; flex-wrap: wrap; gap: 1rem; margin-bottom: 2rem; }
.card { background: #1e293b; border-radius: 0.75rem; padding: 1.25rem 1.5rem;
        flex: 1; min-width: 160px; border: 1px solid #334155; }
.card-label { font-size: 0.72rem; color: #64748b; text-transform: uppercase;
              letter-spacing: .05em; margin-bottom: 0.35rem; }
.card-value { font-size: 1.9rem; font-weight: 700; color: #38bdf8; }
.card-value.green { color: #4ade80; }
.card-value.yellow { color: #fbbf24; }
.card-value.purple { color: #a78bfa; }
.card-value.pct { font-size: 2.4rem; }
section { margin-bottom: 2rem; }
h2 { font-size: 1rem; color: #94a3b8; margin-bottom: 0.75rem;
     border-bottom: 1px solid #1e293b; padding-bottom: 0.4rem; }
.bar-row { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem; }
.bar-label { width: 160px; font-size: 0.82rem; color: #cbd5e1; text-align: right;
             white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bar-track { flex: 1; background: #1e293b; border-radius: 4px; height: 18px; }
.bar-fill { height: 100%; border-radius: 4px; background: #38bdf8;
            display: flex; align-items: center; padding-left: 6px;
            font-size: 0.72rem; color: #0f1117; font-weight: 600;
            min-width: 30px; }
.bar-fill.green { background: #4ade80; }
table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
th { background: #1e293b; color: #94a3b8; text-align: left; padding: 0.5rem 0.75rem;
     font-weight: 600; border-bottom: 1px solid #334155; }
td { padding: 0.45rem 0.75rem; border-bottom: 1px solid #1e293b; color: #cbd5e1; }
tr:hover td { background: #1e293b; }
.badge { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 999px;
         font-size: 0.7rem; font-weight: 600; background: #0369a1; color: #e0f2fe; }
.note { color: #64748b; font-style: italic; font-size: 0.85rem; }
.dim { color: #64748b; }
"""


def _fmt_k(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def _strategy_label(strategy: str) -> str:
    labels = {
        "scoped_source": "Scoped source reads",
        "index_inventory": "Index-only inventory",
        "memory_context": "Memory context",
        "document_context": "Document context",
        "compact_sidecar": "Compact sidecars",
    }
    return labels.get(strategy, strategy.replace("_", " ").title())


_STRATEGY_CATALOG = [
    {
        "strategy": "index_inventory",
        "usage": "Repo/file/class/symbol roster before opening files",
        "typical": "80-95%",
        "notes": "Best first query; avoids source bodies entirely.",
    },
    {
        "strategy": "scoped_source",
        "usage": "feature, impacted, tests, symbol, callers, callees, touchpoints",
        "typical": "60-75%",
        "notes": "Reads only the relevant files instead of the whole repo.",
    },
    {
        "strategy": "memory_context",
        "usage": "mem fetch/search/capture for stable repo knowledge",
        "typical": "70-90%",
        "notes": "Avoids rediscovering decisions, fixes, procedures, and ownership.",
    },
    {
        "strategy": "document_context",
        "usage": "doc fetch/fetch-for/search after Python or Qwen ingest",
        "typical": "60-85%",
        "notes": "Fetches targeted architecture records instead of full docs.",
    },
    {
        "strategy": "compact_sidecar",
        "usage": "compact DSL sidecars for .ai-context, skills, and memory",
        "typical": "30-70% artifact-level; 80-85% full workflow",
        "notes": "Read compact DSL first; decompress/read originals only when needed.",
    },
]


def format_html(summary: dict, repo_root: Path) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    repo_name = repo_root.name

    if summary.get("total_queries", 0) == 0:
        body = f'<p class="note">{html.escape(summary.get("note", "No data."))}</p>'
        return _wrap_html(body, repo_name, ts)

    tq = summary["total_queries"]
    saved = summary["total_tokens_saved_est"]
    naive = summary["total_naive_tokens_est"]
    scope = summary["total_scope_tokens_est"]
    pct = summary["savings_percent"]
    avoided_files = summary["total_files_avoided"]
    avoided_loc = summary["total_loc_avoided"]
    lat = summary["avg_latency_ms"]

    # --- cards ---
    cards_html = f"""
<div class="cards">
  <div class="card"><div class="card-label">Queries ran</div>
    <div class="card-value purple">{tq}</div></div>
  <div class="card"><div class="card-label">Tokens saved (est.)</div>
    <div class="card-value green">{_fmt_k(saved)}</div></div>
  <div class="card"><div class="card-label">Savings %</div>
    <div class="card-value pct green">{pct}%</div></div>
  <div class="card"><div class="card-label">Full workflow estimate</div>
    <div class="card-value pct green">80-85%</div></div>
  <div class="card"><div class="card-label">Naive cost (est.)</div>
    <div class="card-value yellow">{_fmt_k(naive)}</div></div>
  <div class="card"><div class="card-label">Scope cost (est.)</div>
    <div class="card-value">{_fmt_k(scope)}</div></div>
  <div class="card"><div class="card-label">Files avoided</div>
    <div class="card-value">{avoided_files:,}</div></div>
  <div class="card"><div class="card-label">LOC avoided</div>
    <div class="card-value">{_fmt_k(avoided_loc)}</div></div>
  <div class="card"><div class="card-label">Avg latency</div>
    <div class="card-value">{lat} ms</div></div>
</div>"""

    compact = summary.get("compact_sidecars", {})
    compact_html = ""
    if compact.get("total", 0):
        compact_html = f"""
<section><h2>Compact sidecar savings</h2>
<div class="cards">
  <div class="card"><div class="card-label">Sidecars built</div>
    <div class="card-value purple">{compact.get('total', 0):,}</div></div>
  <div class="card"><div class="card-label">Source tokens</div>
    <div class="card-value yellow">{_fmt_k(compact.get('source_tokens_est', 0))}</div></div>
  <div class="card"><div class="card-label">DSL tokens</div>
    <div class="card-value">{_fmt_k(compact.get('dsl_tokens_est', 0))}</div></div>
  <div class="card"><div class="card-label">Compact saving</div>
    <div class="card-value pct green">{compact.get('saving_percent_est', 0)}%</div></div>
</div></section>"""

    # --- command bars ---
    by_cmd = summary.get("by_command", {})
    max_saved = max((v["tokens_saved"] for v in by_cmd.values()), default=1) or 1
    bar_rows: list = []
    for cmd, stats in by_cmd.items():
        pct_w = int(100 * stats["tokens_saved"] / max_saved)
        bar_rows.append(
            f'<div class="bar-row">'
            f'<div class="bar-label">{html.escape(cmd)}</div>'
            f'<div class="bar-track"><div class="bar-fill green" style="width:{pct_w}%">'
            f'{_fmt_k(stats["tokens_saved"])} tkn</div></div>'
            f'<span style="color:#64748b;font-size:.75rem">{stats["queries"]}q</span>'
            f'</div>'
        )
    bars_html = f'<section><h2>Tokens saved by command</h2>{"".join(bar_rows)}</section>'

    # --- strategy bars ---
    by_strategy = summary.get("by_strategy", {})
    max_strategy_saved = max((v["tokens_saved"] for v in by_strategy.values()), default=1) or 1
    strategy_rows: list = []
    for strategy, stats in by_strategy.items():
        pct_w = int(100 * stats["tokens_saved"] / max_strategy_saved)
        strategy_rows.append(
            f'<div class="bar-row">'
            f'<div class="bar-label">{html.escape(_strategy_label(strategy))}</div>'
            f'<div class="bar-track"><div class="bar-fill green" style="width:{pct_w}%">'
            f'{_fmt_k(stats["tokens_saved"])} tkn</div></div>'
            f'<span style="color:#64748b;font-size:.75rem">{stats["queries"]}q</span>'
            f'</div>'
        )
    strategies_html = (
        f'<section><h2>Tokens saved by strategy</h2>{"".join(strategy_rows)}</section>'
        if strategy_rows else ""
    )

    catalog_rows = []
    for item in _STRATEGY_CATALOG:
        catalog_rows.append(
            f"<tr>"
            f"<td><strong>{html.escape(_strategy_label(item['strategy']))}</strong></td>"
            f"<td>{html.escape(item['usage'])}</td>"
            f"<td>{html.escape(item['typical'])}</td>"
            f"<td class='dim'>{html.escape(item['notes'])}</td>"
            f"</tr>"
        )
    catalog_html = f"""
<section><h2>Strategy catalog and expected savings</h2>
<table><thead><tr>
  <th>Strategy</th><th>Usual usage</th><th>Typical saving</th><th>Notes</th>
</tr></thead><tbody>{"".join(catalog_rows)}</tbody></table>
<p class="note" style="margin-top:.75rem">
  Scope-only workflows usually land around 65-75%. Combining index inventory,
  scoped source reads, memory/doc retrieval, and compact sidecars is expected to
  reach up to about 80-85% on codebase-context tasks.
</p></section>"""

    # --- recent queries table ---
    recent = summary.get("recent_queries", [])
    rows: list = []
    for q in recent[:20]:
        rows.append(
            f"<tr>"
            f"<td>{html.escape(q.get('ts',''))}</td>"
            f"<td><span class='badge'>{html.escape(q.get('cmd',''))}</span></td>"
            f"<td>{q.get('result_files',0)}</td>"
            f"<td>{_fmt_k(q.get('tokens_saved_est',0))}</td>"
            f"<td>{q.get('latency_ms',0)} ms</td>"
            f"<td style='color:#64748b;font-size:.75rem'>"
            f"{html.escape(str(q.get('args',{}))[:60])}</td>"
            f"</tr>"
        )
    table_html = f"""
<section><h2>Recent queries</h2>
<table><thead><tr>
  <th>Timestamp</th><th>Command</th><th>Files returned</th>
  <th>Tokens saved</th><th>Latency</th><th>Args</th>
</tr></thead><tbody>{"".join(rows)}</tbody></table></section>"""

    body = cards_html + compact_html + bars_html + strategies_html + catalog_html + table_html
    return _wrap_html(body, repo_name, ts)


# ---------------------------------------------------------------------------
# Global report — terminal
# ---------------------------------------------------------------------------

def format_global_terminal(g: dict) -> str:
    lines: list = []
    a = lines.append
    t = g.get("totals", {})
    repos = g.get("repos", [])

    a("=" * 68)
    a("  SCOPE INTELLIGENCE - GLOBAL TOKEN SAVINGS REPORT")
    a("=" * 68)
    a(f"  Repos tracked         : {t.get('repos', 0)}")
    a(f"  Total queries         : {t.get('queries', 0):,}")
    a(f"  Tokens saved (est.)   : {t.get('tokens_saved', 0):,}")
    a(f"  Naive cost (est.)     : {t.get('naive_tokens', 0):,}")
    a(f"  Scope cost (est.)     : {t.get('scope_tokens', 0):,}")
    a(f"  Global savings        : {t.get('savings_percent', 0)}%")
    a(f"  Files avoided         : {t.get('files_avoided', 0):,}  "
      f"({t.get('loc_avoided', 0):,} LOC)")
    a("")
    a("  Per-repo breakdown:")
    a(f"  {'Repo':<22} {'Queries':>7}  {'Saved(tkn)':>11}  {'Savings%':>9}  "
      f"{'Memory':>7}")
    a("  " + "-" * 62)
    for r in repos:
        mem_total = r.get("memory", {}).get("total", 0)
        note = r.get("note", "")
        if note:
            a(f"  {r['name']:<22} {'—':>7}  {'—':>11}  {'—':>9}  {note}")
        else:
            a(f"  {r['name']:<22} {r['total_queries']:>7,}  "
              f"{r['tokens_saved']:>11,}  {r['savings_percent']:>8.1f}%  "
              f"{mem_total:>5} mem")
    a("")
    a("  By command (all repos):")
    for cmd, stats in g.get("by_command", {}).items():
        bar = "#" * min(int(stats["tokens_saved"] / 200), 28)
        a(f"    {cmd:<18} {stats['queries']:>4} queries  "
          f"~{stats['tokens_saved']:>8,} tkn  {bar}")
    a("")
    a("  Recent queries (newest first, all repos):")
    a(f"  {'Timestamp':<22} {'Repo':<16} {'Command':<14} {'Saved(tkn)':<12} ms")
    a("  " + "-" * 72)
    for q in g.get("recent_queries", [])[:15]:
        a(f"  {q.get('ts',''):<22} {q.get('_repo',''):<16} "
          f"{q.get('cmd',''):<14} {q.get('tokens_saved_est', 0):<12,} "
          f"{q.get('latency_ms', 0)}")
    a("=" * 68)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Global report — HTML
# ---------------------------------------------------------------------------

_GLOBAL_EXTRA_CSS = """
.repo-table { width:100%; border-collapse:collapse; margin-bottom:2rem; font-size:0.83rem; }
.repo-table th { background:#1e293b; color:#94a3b8; text-align:left;
                 padding:0.5rem 0.75rem; font-weight:600; border-bottom:1px solid #334155; }
.repo-table td { padding:0.45rem 0.75rem; border-bottom:1px solid #1e293b; color:#cbd5e1; }
.repo-table tr:hover td { background:#1e293b; }
.savings-bar { height:10px; border-radius:4px; background:#38bdf8;
               display:inline-block; vertical-align:middle; }
.dim { color:#64748b; }
"""

def format_global_html(g: dict) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    t = g.get("totals", {})
    repos = g.get("repos", [])

    # --- global stat cards ---
    cards = f"""
<div class="cards">
  <div class="card"><div class="card-label">Repos tracked</div>
    <div class="card-value purple">{t.get('repos', 0)}</div></div>
  <div class="card"><div class="card-label">Total queries</div>
    <div class="card-value">{t.get('queries', 0):,}</div></div>
  <div class="card"><div class="card-label">Tokens saved (est.)</div>
    <div class="card-value green">{_fmt_k(t.get('tokens_saved', 0))}</div></div>
  <div class="card"><div class="card-label">Global savings %</div>
    <div class="card-value pct green">{t.get('savings_percent', 0)}%</div></div>
  <div class="card"><div class="card-label">Naive cost (est.)</div>
    <div class="card-value yellow">{_fmt_k(t.get('naive_tokens', 0))}</div></div>
  <div class="card"><div class="card-label">Scope cost (est.)</div>
    <div class="card-value">{_fmt_k(t.get('scope_tokens', 0))}</div></div>
  <div class="card"><div class="card-label">Files avoided</div>
    <div class="card-value">{t.get('files_avoided', 0):,}</div></div>
  <div class="card"><div class="card-label">LOC avoided</div>
    <div class="card-value">{_fmt_k(t.get('loc_avoided', 0))}</div></div>
</div>"""

    # --- per-repo table ---
    max_saved = max((r["tokens_saved"] for r in repos), default=1) or 1
    repo_rows: list = []
    for r in repos:
        pct_bar = int(80 * r["tokens_saved"] / max_saved)
        mem = r.get("memory", {})
        mem_str = (f"{mem['total']} ({mem.get('open',0)} open)"
                   if mem.get("total", 0) else "—")
        note = r.get("note", "")
        if note:
            repo_rows.append(
                f"<tr><td><strong>{html.escape(r['name'])}</strong><br>"
                f"<span class='dim' style='font-size:.72rem'>{html.escape(r['path'])}</span></td>"
                f"<td colspan='6' class='dim'>{html.escape(note)}</td></tr>"
            )
        else:
            bar_html = (f'<div class="savings-bar" style="width:{pct_bar}px"></div>'
                        f' {_fmt_k(r["tokens_saved"])}')
            repo_rows.append(
                f"<tr>"
                f"<td><strong>{html.escape(r['name'])}</strong><br>"
                f"<span class='dim' style='font-size:.72rem'>{html.escape(r['path'])}</span></td>"
                f"<td>{r['total_queries']:,}</td>"
                f"<td>{bar_html}</td>"
                f"<td>{r['savings_percent']}%</td>"
                f"<td>{_fmt_k(r['naive_tokens'])}</td>"
                f"<td>{r['avg_latency_ms']} ms</td>"
                f"<td>{mem_str}</td>"
                f"</tr>"
            )
    repo_table = f"""
<section><h2>Per-repo breakdown</h2>
<table class="repo-table"><thead><tr>
  <th>Repo</th><th>Queries</th><th>Tokens saved</th>
  <th>Savings %</th><th>Naive cost</th><th>Avg latency</th><th>Memory</th>
</tr></thead><tbody>{"".join(repo_rows)}</tbody></table></section>"""

    # --- by-command bars ---
    by_cmd = g.get("by_command", {})
    max_cmd_saved = max((v["tokens_saved"] for v in by_cmd.values()), default=1) or 1
    cmd_bars: list = []
    for cmd, stats in by_cmd.items():
        w = int(100 * stats["tokens_saved"] / max_cmd_saved)
        cmd_bars.append(
            f'<div class="bar-row">'
            f'<div class="bar-label">{html.escape(cmd)}</div>'
            f'<div class="bar-track"><div class="bar-fill green" style="width:{w}%">'
            f'{_fmt_k(stats["tokens_saved"])} tkn</div></div>'
            f'<span style="color:#64748b;font-size:.75rem">{stats["queries"]}q</span>'
            f'</div>'
        )
    cmd_section = (f'<section><h2>Tokens saved by command (all repos)</h2>'
                   f'{"".join(cmd_bars)}</section>')

    # --- recent queries across all repos ---
    recent = g.get("recent_queries", [])
    rows: list = []
    for q in recent[:20]:
        repo_badge = (f'<span class="badge" style="background:#1d4ed8">'
                      f'{html.escape(q.get("_repo", ""))}</span>')
        rows.append(
            f"<tr>"
            f"<td>{html.escape(q.get('ts', ''))}</td>"
            f"<td>{repo_badge}</td>"
            f"<td><span class='badge'>{html.escape(q.get('cmd', ''))}</span></td>"
            f"<td>{q.get('result_files', 0)}</td>"
            f"<td>{_fmt_k(q.get('tokens_saved_est', 0))}</td>"
            f"<td>{q.get('latency_ms', 0)} ms</td>"
            f"</tr>"
        )
    recent_table = f"""
<section><h2>Recent queries — all repos</h2>
<table><thead><tr>
  <th>Timestamp</th><th>Repo</th><th>Command</th>
  <th>Files returned</th><th>Tokens saved</th><th>Latency</th>
</tr></thead><tbody>{"".join(rows)}</tbody></table></section>"""

    body = cards + repo_table + cmd_section + recent_table
    css = _CSS + _GLOBAL_EXTRA_CSS
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scope Intelligence - Global Report</title>
<style>{css}</style>
</head>
<body>
<h1>Scope Intelligence - Global Token Savings Report</h1>
<div class="sub">All repos &nbsp;|&nbsp; Generated: {ts}</div>
{body}
<p class="note" style="margin-top:2rem">
  Estimates assume 10 tokens/LOC. Naive baseline = reading every indexed file per query.
  Actual savings depend on session context size.
</p>
</body>
</html>"""


def _wrap_html(body: str, repo_name: str, ts: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scope Intelligence — Token Savings Report</title>
<style>{_CSS}</style>
</head>
<body>
<h1>Scope Intelligence — Token Savings Report</h1>
<div class="sub">Repo: <strong>{html.escape(repo_name)}</strong> &nbsp;|&nbsp; Generated: {ts}</div>
{body}
<p class="note" style="margin-top:2rem">
  Estimates assume 10 tokens/LOC (50 chars/line, 5 chars/token).
  Naive baseline = reading every indexed file. Actual savings depend on session context size.
</p>
</body>
</html>"""
