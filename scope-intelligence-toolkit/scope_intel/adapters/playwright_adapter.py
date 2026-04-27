"""Playwright adapter — sits *in front of* the JS adapter for spec files.

Recognises `.spec.{js,ts,...}` or files importing `@playwright/test`. Reuses
the JS adapter's symbol/import extraction but tags the file with the
`playwright` framework so downstream queries can isolate browser tests.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Optional

from .base import LanguageAdapter, ParsedFile, ParsedTest
from .javascript_adapter import JavaScriptAdapter


PW_IMPORT_RE = re.compile(r'@playwright/test')
TEST_BLOCK_RE = re.compile(r'\b(?:test|it)\s*\(\s*["\'`]([^"\'`]+)["\'`]')


class PlaywrightAdapter(LanguageAdapter):
    name = "playwright"
    extensions = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")

    def __init__(self) -> None:
        self._js = JavaScriptAdapter()

    def matches(self, path: Path) -> bool:
        if path.suffix.lower() not in self.extensions:
            return False
        # Cheap path-based hint first.
        n = path.name.lower()
        if n.endswith((".spec.js", ".spec.ts", ".spec.jsx", ".spec.tsx")):
            return True
        parts = {p.lower() for p in path.parts}
        if {"e2e", "playwright", "tests-e2e"} & parts:
            # need to confirm by content, fall through
            pass
        else:
            return False
        try:
            head = path.read_text(encoding="utf-8", errors="ignore")[:2000]
        except OSError:
            return False
        return bool(PW_IMPORT_RE.search(head))

    def is_test(self, path: Path) -> bool:
        return True

    def parse_file(self, path: Path, content: str) -> ParsedFile:
        parsed = self._js.parse_file(path, content)
        parsed.language = self.name
        cases = [m.group(1) for m in TEST_BLOCK_RE.finditer(content)]
        parsed.test = ParsedTest(framework="playwright",
                                 test_cases=cases,
                                 covers_hints=parsed.imports_raw[:])
        return parsed

    def resolve_import(self, raw: str, from_file: Path, repo_root: Path,
                       known_files: Iterable[Path]) -> Optional[str]:
        return self._js.resolve_import(raw, from_file, repo_root, known_files)

    def external_deps(self, repo_root: Path) -> list:
        # Already covered by the JS adapter — avoid double-counting.
        return []
