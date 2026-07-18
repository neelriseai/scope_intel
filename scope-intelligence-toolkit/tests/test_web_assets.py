from __future__ import annotations

from pathlib import Path

import pytest

from scope_intel.core import store
from scope_intel.core.indexer import build_index
from scope_intel.core.query_engine import get_feature_scope, get_related_tests


@pytest.fixture()
def web_repo(tmp_path: Path) -> Path:
    (tmp_path / "web" / "runtime").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "web" / "index.html").write_text(
        """<!doctype html>
<link rel="stylesheet" href="styles.css?v=1">
<link rel="preload" href="runtime/chat.js" as="script">
<script src="https://example.invalid/external.js"></script>
<script src="app.js?v=2"></script>
""",
        encoding="utf-8",
    )
    (tmp_path / "web" / "styles.css").write_text(
        "@import './theme.css';\n.avatar { background: url('../assets/avatar.png'); }\n",
        encoding="utf-8",
    )
    (tmp_path / "web" / "theme.css").write_text(":root { color: black; }\n", encoding="utf-8")
    (tmp_path / "web" / "app.js").write_text("function boot() { return true; }\n", encoding="utf-8")
    (tmp_path / "web" / "runtime" / "chat.js").write_text(
        "function createChatRuntime() { return {}; }\n",
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_web_shell.py").write_text(
        """from pathlib import Path

def test_static_web_shell():
    root = Path(__file__).resolve().parents[1]
    html = (root / "web" / "index.html").read_text()
    css = (root / "web" / "styles.css").read_text()
    app = (root / "web" / "app.js").read_text()
    chat = (root / "web" / "runtime" / "chat.js").read_text()
    assert html and css and app and chat
""",
        encoding="utf-8",
    )
    store.ensure_index_dir(tmp_path)
    store.write_json(tmp_path, "config", store.default_config())
    build_index(tmp_path)
    return tmp_path


def test_html_and_css_assets_join_web_feature(web_repo: Path) -> None:
    files = store.read_json(web_repo, "dependencies", {"files": {}})["files"]

    assert files["web/index.html"]["language"] == "html"
    assert files["web/styles.css"]["language"] == "css"
    assert files["web/index.html"]["feature"] == "web"
    assert files["web/styles.css"]["feature"] == "web"
    assert set(files["web/index.html"]["imports"]) == {
        "web/app.js",
        "web/runtime/chat.js",
        "web/styles.css",
    }
    assert files["web/styles.css"]["imports"] == ["web/theme.css"]
    assert "web/index.html" in files["web/app.js"]["imported_by"]


def test_python_static_path_hints_create_coverage_edges(web_repo: Path) -> None:
    tests = store.read_json(web_repo, "tests", {"tests": []})["tests"]
    record = next(test for test in tests if test["file"] == "tests/test_web_shell.py")

    assert set(record["covers_files"]) == {
        "web/app.js",
        "web/index.html",
        "web/runtime/chat.js",
        "web/styles.css",
    }
    assert "web" in record["covers_features"]


def test_web_feature_returns_assets_and_static_test(web_repo: Path) -> None:
    feature = get_feature_scope(web_repo, "web")
    related = get_related_tests(web_repo, feature="web")

    assert {"web/index.html", "web/styles.css", "web/app.js"}.issubset(set(feature["files"]))
    assert any(test["file"] == "tests/test_web_shell.py" for test in feature["tests"])
    test_record = next(test for test in feature["tests"] if test["file"] == "tests/test_web_shell.py")
    assert test_record["case_count"] == 1
    assert len(test_record["cases"]) == 1
    assert any(match["file"] == "tests/test_web_shell.py" for match in related["matches"])

