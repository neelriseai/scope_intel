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
    a(f"  Files avoided         : {summary['total_files_avoided']:,}  ({summary['total_loc_avoided']:,} LOC)")
    a(f"  Avg query latency     : {summary['avg_latency_ms']} ms")
    a("")
    a("  By command:")
    for cmd, stats in summary.get("by_command", {}).items():
        bar = "#" * min(int(stats["queries"] * 2), 30)
        a(f"    {cmd:<18} {stats['queries']:>4} queries   "
          f"~{stats['tokens_saved']:>7,} tkn saved   {bar}")
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
"""


def _fmt_k(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


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

    body = cards_html + bars_html + table_html
    return _wrap_html(body, repo_name, ts)


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
