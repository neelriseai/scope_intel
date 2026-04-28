"""Compact human-readable summaries derived from the index. No LLM calls."""
from __future__ import annotations

from collections import Counter
from pathlib import Path


def build_repo_summary(repo_root: Path, files_index: dict, symbols: list,
                       tests: list, features: list) -> dict:
    languages = Counter(e.get("language") for e in files_index.values() if e.get("language"))
    test_languages = Counter(t.get("language") for t in tests if t.get("language"))
    test_frameworks = Counter(t.get("framework") for t in tests if t.get("framework"))

    top_features = sorted(features, key=lambda f: -f.get("file_count", 0))[:10]
    largest_files = sorted(files_index.items(),
                           key=lambda kv: -(kv[1].get("loc") or 0))[:10]
    most_imported = sorted(files_index.items(),
                           key=lambda kv: -len(kv[1].get("imported_by") or []))[:10]

    return {
        "repo_root": str(repo_root),
        "totals": {
            "files": len(files_index),
            "symbols": len(symbols),
            "tests": len(tests),
            "features": len(features),
        },
        "languages": dict(languages),
        "test_frameworks": dict(test_frameworks),
        "test_languages": dict(test_languages),
        "top_features": [
            {
                "id": f["id"],
                "files": f["file_count"],
                "symbols": f["symbol_count"],
                "languages": f.get("languages", []),
                "tests": len(f.get("related_tests") or []),
            } for f in top_features
        ],
        "largest_files": [
            {"file": k, "loc": v.get("loc"), "language": v.get("language")}
            for k, v in largest_files
        ],
        "most_imported_files": [
            {"file": k, "imported_by": len(v.get("imported_by") or []),
             "language": v.get("language")}
            for k, v in most_imported if v.get("imported_by")
        ],
    }


def feature_one_liner(feature: dict) -> str:
    parts = [
        f"{feature['id']}",
        f"{feature.get('file_count', 0)} files",
        f"{feature.get('symbol_count', 0)} symbols",
        f"langs={','.join(feature.get('languages', [])) or '?'}",
    ]
    deps = feature.get("depends_on_features") or []
    if deps:
        parts.append(f"depends_on={','.join(deps)}")
    tests = feature.get("related_tests") or []
    if tests:
        parts.append(f"tests={len(tests)}")
    return " | ".join(parts)
