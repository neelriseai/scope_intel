"""Compact sidecar artifacts for agent-facing context.

The original files remain canonical.  Each compact sidecar has two parts:

  * a readable, token-light DSL block intended for agents
  * an exact zlib+base64 payload used for lossless validation/decompression

That lets agents read the cheap representation first while tests can prove the
source text is still recoverable byte-for-byte.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import time
import zlib
from pathlib import Path
from typing import Iterable, Optional

from . import store

VERSION = "scope-compact-v1"
DSL_MARKER = "--- dsl ---"
PAYLOAD_MARKER = "--- payload.zlib.b64 ---"

AI_CONTEXT_EXTS = {".md", ".txt", ".json"}

_DROP_WORDS = {
    "a", "an", "the", "that", "very", "quite", "really", "basically",
    "essentially", "simply", "currently",
}
_PHRASE_REPLACEMENTS = (
    (re.compile(r"\bin order to\b", re.I), "to"),
    (re.compile(r"\bit is important to\b", re.I), "must"),
    (re.compile(r"\bshould be able to\b", re.I), "can"),
    (re.compile(r"\bis responsible for\b", re.I), "handles"),
    (re.compile(r"\bwill be used to\b", re.I), "used to"),
)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _short_sha(text: str) -> str:
    return _sha(text)[:12]


def _compress_payload(text: str) -> str:
    raw = zlib.compress(text.encode("utf-8"), level=9)
    return base64.b64encode(raw).decode("ascii")


def _decompress_payload(payload: str) -> str:
    raw = base64.b64decode(payload.encode("ascii"))
    return zlib.decompress(raw).decode("utf-8")


def _compact_phrase(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    for pattern, repl in _PHRASE_REPLACEMENTS:
        text = pattern.sub(repl, text)
    words = []
    for word in text.split():
        bare = word.strip(".,;:()[]{}").lower()
        if bare in _DROP_WORDS:
            continue
        words.append(word)
    return " ".join(words).strip()


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def render_compact_dsl(text: str, *, source: str = "") -> str:
    """Render markdown-ish text as a compact, readable DSL.

    The DSL is intentionally deterministic and conservative: it keeps names,
    paths, code identifiers, numbers, bullets, tables, and headings.  It only
    strips predictable prose glue in paragraph lines.
    """
    out: list[str] = [f"@doc path={source or '?'} sha={_short_sha(text)}"]
    in_code = False
    code_lang = ""
    code_lines = 0
    code_hash = hashlib.sha256()

    def _flush_code() -> None:
        nonlocal code_lines, code_hash, code_lang
        if code_lines:
            out.append(f"!CODE lang={code_lang or '-'} lines={code_lines} sha={code_hash.hexdigest()[:12]}")
        code_lines = 0
        code_hash = hashlib.sha256()
        code_lang = ""

    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("```"):
            if in_code:
                _flush_code()
                in_code = False
            else:
                in_code = True
                code_lang = stripped.strip("`").strip()
            continue

        if in_code:
            code_lines += 1
            code_hash.update((line + "\n").encode("utf-8"))
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            level = len(heading.group(1))
            out.append(f"!H{level} {_compact_phrase(heading.group(2))}")
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if any(c and set(c) != {"-"} for c in cells):
                out.append("!T " + " | ".join(cells))
            continue

        bullet = re.match(r"^[-*+]\s+(.+)$", stripped)
        if bullet:
            out.append("!B " + _compact_phrase(bullet.group(1)))
            continue

        numbered = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        if numbered:
            out.append("!N " + _compact_phrase(numbered.group(1)))
            continue

        if stripped.startswith(">"):
            stripped = stripped.lstrip("> ").strip()

        for sentence in _split_sentences(stripped):
            compact = _compact_phrase(sentence)
            if compact:
                out.append("!P " + compact)

    if in_code:
        _flush_code()

    return "\n".join(out).strip() + "\n"


def make_sidecar_text(source_text: str, *, source_rel: str, kind: str) -> str:
    dsl = render_compact_dsl(source_text, source=source_rel)
    meta = {
        "version": VERSION,
        "kind": kind,
        "source": source_rel,
        "source_sha256": _sha(source_text),
        "source_chars": len(source_text),
        "source_tokens_est": estimate_tokens(source_text),
        "dsl_chars": len(dsl),
        "dsl_tokens_est": estimate_tokens(dsl),
        "payload": "zlib+base64",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return (
        json.dumps(meta, sort_keys=True, ensure_ascii=False)
        + "\n"
        + DSL_MARKER
        + "\n"
        + dsl
        + PAYLOAD_MARKER
        + "\n"
        + _compress_payload(source_text)
        + "\n"
    )


def parse_sidecar(text: str) -> dict:
    first, sep, rest = text.partition("\n")
    if not sep:
        return {"error": "invalid compact file: missing metadata"}
    try:
        meta = json.loads(first)
    except json.JSONDecodeError as exc:
        return {"error": f"invalid compact metadata: {exc}"}
    if DSL_MARKER not in rest or PAYLOAD_MARKER not in rest:
        return {"error": "invalid compact file: missing markers"}
    dsl_part = rest.split(DSL_MARKER, 1)[1].split(PAYLOAD_MARKER, 1)[0].strip()
    payload = rest.split(PAYLOAD_MARKER, 1)[1].strip()
    try:
        original = _decompress_payload(payload)
    except (ValueError, zlib.error) as exc:
        return {"error": f"payload decode failed: {exc}"}
    return {"meta": meta, "dsl": dsl_part, "content": original}


def compact_path_for(repo_root: Path, source: Path, *, kind: str) -> Path:
    rel = source.relative_to(repo_root)
    if kind == "ai-context":
        compact_root = repo_root / ".ai-context" / "compact"
        rel_under = rel.relative_to(".ai-context")
        return compact_root / rel_under.with_suffix(rel_under.suffix + ".scope")
    if kind == "skill":
        compact_root = repo_root / ".agents" / "compact"
        rel_under = rel.relative_to(".agents")
        return compact_root / rel_under.with_suffix(rel_under.suffix + ".scope")
    if kind == "memory":
        return store.index_dir(repo_root) / "mempalace.compact.scope"
    return repo_root / ".scope-intelligence" / "compact" / rel.with_suffix(rel.suffix + ".scope")


def _ai_context_sources(repo_root: Path) -> Iterable[tuple[Path, str]]:
    ai_ctx = repo_root / ".ai-context"
    if not ai_ctx.exists():
        return []
    out: list[tuple[Path, str]] = []
    for p in sorted(ai_ctx.rglob("*")):
        if not p.is_file() or "compact" in p.relative_to(ai_ctx).parts:
            continue
        if p.suffix.lower() in AI_CONTEXT_EXTS:
            out.append((p, "ai-context"))
    return out


def _skill_sources(repo_root: Path) -> Iterable[tuple[Path, str]]:
    root = repo_root / ".agents" / "skills"
    if not root.exists():
        return []
    return [(p, "skill") for p in sorted(root.rglob("SKILL.md")) if p.is_file()]


def _memory_sources(repo_root: Path) -> Iterable[tuple[Path, str]]:
    path = store.mempalace_path(repo_root)
    if not path.exists():
        return []
    return [(path, "memory")]


def iter_sources(repo_root: Path, target: str) -> list[tuple[Path, str]]:
    if target == "ai-context":
        return list(_ai_context_sources(repo_root))
    if target == "skills":
        return list(_skill_sources(repo_root))
    if target == "memory":
        return list(_memory_sources(repo_root))
    if target == "all":
        return list(_ai_context_sources(repo_root)) + list(_skill_sources(repo_root)) + list(_memory_sources(repo_root))
    return []


def build_compact_artifacts(
    repo_root: Path,
    *,
    target: str = "ai-context",
    overwrite: bool = True,
) -> dict:
    repo_root = Path(repo_root).resolve()
    sources = iter_sources(repo_root, target)
    written: list[dict] = []
    skipped: list[dict] = []

    if not sources:
        return {"target": target, "written": [], "skipped": [], "total_written": 0}

    for source, kind in sources:
        try:
            text = source.read_text(encoding="utf-8")
        except OSError as exc:
            skipped.append({"source": str(source), "reason": str(exc)})
            continue
        out_path = compact_path_for(repo_root, source, kind=kind)
        if out_path.exists() and not overwrite:
            skipped.append({"source": str(source.relative_to(repo_root)), "reason": "exists"})
            continue
        sidecar = make_sidecar_text(
            text,
            source_rel=str(source.relative_to(repo_root)).replace("\\", "/"),
            kind=kind,
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(sidecar, encoding="utf-8")
        parsed = parse_sidecar(sidecar)
        meta = parsed.get("meta", {})
        written.append({
            "source": meta.get("source"),
            "compact": str(out_path.relative_to(repo_root)).replace("\\", "/"),
            "kind": kind,
            "source_tokens": meta.get("source_tokens_est", 0),
            "dsl_tokens": meta.get("dsl_tokens_est", 0),
            "saved_tokens": max(meta.get("source_tokens_est", 0) - meta.get("dsl_tokens_est", 0), 0),
        })

    total_source = sum(i["source_tokens"] for i in written)
    total_dsl = sum(i["dsl_tokens"] for i in written)
    return {
        "target": target,
        "total_sources": len(sources),
        "total_written": len(written),
        "total_skipped": len(skipped),
        "source_tokens_est": total_source,
        "dsl_tokens_est": total_dsl,
        "saved_tokens_est": max(total_source - total_dsl, 0),
        "saving_percent_est": round(100 * (total_source - total_dsl) / total_source, 1) if total_source else 0.0,
        "written": written,
        "skipped": skipped,
    }


def iter_sidecars(repo_root: Path, target: str = "all") -> list[Path]:
    repo_root = Path(repo_root)
    roots: list[Path] = []
    if target in ("ai-context", "all"):
        roots.append(repo_root / ".ai-context" / "compact")
    if target in ("skills", "all"):
        roots.append(repo_root / ".agents" / "compact")
    if target in ("memory", "all"):
        path = store.index_dir(repo_root) / "mempalace.compact.scope"
        if path.exists():
            return [path] if target == "memory" else [path] + [p for r in roots for p in r.rglob("*.scope") if r.exists()]
    out: list[Path] = []
    for root in roots:
        if root.exists():
            out.extend(sorted(root.rglob("*.scope")))
    return out


def validate_compact_artifacts(repo_root: Path, *, target: str = "all") -> dict:
    repo_root = Path(repo_root).resolve()
    results: list[dict] = []
    for sidecar in iter_sidecars(repo_root, target):
        parsed = parse_sidecar(sidecar.read_text(encoding="utf-8"))
        if "error" in parsed:
            results.append({"compact": str(sidecar), "ok": False, "error": parsed["error"]})
            continue
        meta = parsed["meta"]
        source = repo_root / meta.get("source", "")
        if not source.exists():
            results.append({
                "compact": str(sidecar.relative_to(repo_root)).replace("\\", "/"),
                "source": meta.get("source", ""),
                "ok": False,
                "error": "source missing",
            })
            continue
        current = source.read_text(encoding="utf-8")
        content = parsed["content"]
        same_hash = _sha(content) == meta.get("source_sha256")
        same_current = content == current
        results.append({
            "compact": str(sidecar.relative_to(repo_root)).replace("\\", "/"),
            "source": meta.get("source", ""),
            "kind": meta.get("kind"),
            "ok": same_hash and same_current,
            "payload_matches_recorded_hash": same_hash,
            "payload_matches_current_source": same_current,
            "source_tokens": meta.get("source_tokens_est", 0),
            "dsl_tokens": meta.get("dsl_tokens_est", 0),
        })
    ok = all(r.get("ok") for r in results)
    return {
        "target": target,
        "ok": ok,
        "total": len(results),
        "failed": sum(1 for r in results if not r.get("ok")),
        "results": results,
    }


def compact_stats(repo_root: Path, *, target: str = "all") -> dict:
    repo_root = Path(repo_root).resolve()
    rows: list[dict] = []
    for sidecar in iter_sidecars(repo_root, target):
        parsed = parse_sidecar(sidecar.read_text(encoding="utf-8"))
        if "error" in parsed:
            rows.append({"compact": str(sidecar), "error": parsed["error"]})
            continue
        meta = parsed["meta"]
        rows.append({
            "compact": str(sidecar.relative_to(repo_root)).replace("\\", "/"),
            "source": meta.get("source"),
            "kind": meta.get("kind"),
            "source_tokens": meta.get("source_tokens_est", 0),
            "dsl_tokens": meta.get("dsl_tokens_est", 0),
            "saved_tokens": max(meta.get("source_tokens_est", 0) - meta.get("dsl_tokens_est", 0), 0),
        })
    source_tokens = sum(r.get("source_tokens", 0) for r in rows)
    dsl_tokens = sum(r.get("dsl_tokens", 0) for r in rows)
    return {
        "target": target,
        "total": len(rows),
        "source_tokens_est": source_tokens,
        "dsl_tokens_est": dsl_tokens,
        "saved_tokens_est": max(source_tokens - dsl_tokens, 0),
        "saving_percent_est": round(100 * (source_tokens - dsl_tokens) / source_tokens, 1) if source_tokens else 0.0,
        "files": rows,
    }


def decompress_compact_file(path: Path) -> dict:
    parsed = parse_sidecar(Path(path).read_text(encoding="utf-8"))
    if "error" in parsed:
        return parsed
    return {
        "meta": parsed["meta"],
        "content": parsed["content"],
        "chars": len(parsed["content"]),
        "tokens": estimate_tokens(parsed["content"]),
    }


def get_inventory(
    repo_root: Path,
    *,
    feature: Optional[str] = None,
    include_symbols: bool = True,
) -> dict:
    """Return files/classes/symbols from the existing index, without reading source."""
    if not store.is_initialized(repo_root):
        return {"error": "repo not indexed - run scope init && scope index first"}
    deps = store.read_json(repo_root, "dependencies", {"files": {}})
    symbols_data = store.read_json(repo_root, "symbols", {"symbols": []})
    files_index = deps.get("files", {})
    symbols = symbols_data.get("symbols", [])

    if feature:
        files_index = {
            path: meta for path, meta in files_index.items()
            if meta.get("feature") == feature
        }
        allowed = set(files_index)
        symbols = [s for s in symbols if s.get("file") in allowed]

    classes = [s for s in symbols if s.get("kind") == "class"]
    functions = [s for s in symbols if s.get("kind") in ("function", "method")]
    files = [
        {
            "file": path,
            "language": meta.get("language"),
            "feature": meta.get("feature"),
            "loc": meta.get("loc", 0),
            "symbols": len(meta.get("symbols", [])),
        }
        for path, meta in sorted(files_index.items())
    ]
    result: dict = {
        "repo": str(Path(repo_root).resolve()),
        "feature": feature,
        "totals": {
            "files": len(files),
            "classes": len(classes),
            "functions": len(functions),
            "symbols": len(symbols),
        },
        "files": files,
        "classes": [
            {
                "name": s.get("name"),
                "qualified_name": s.get("qualified_name"),
                "file": s.get("file"),
                "line": s.get("line"),
                "bases": s.get("bases", []),
            }
            for s in classes
        ],
    }
    if include_symbols:
        result["symbols"] = [
            {
                "name": s.get("name"),
                "qualified_name": s.get("qualified_name"),
                "kind": s.get("kind"),
                "file": s.get("file"),
                "line": s.get("line"),
                "feature": s.get("feature"),
            }
            for s in symbols
        ]
    return result
