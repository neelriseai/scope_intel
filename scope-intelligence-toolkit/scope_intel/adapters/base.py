"""Language adapter contract.

Each adapter is responsible for *one* language family. It tells the indexer:
  - which files it can parse (`matches`)
  - what symbols/imports/tests live in a parsed file (`parse_file`)
  - whether a file looks like a test file (`is_test`)
  - how to resolve a raw import string back to a file inside the repo (`resolve_import`)

Adapters never store source code in the index — only locations, names, and edges.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional


@dataclass
class ParsedSymbol:
    name: str
    kind: str              # class | function | method | interface | enum
    line: int
    qualified_name: Optional[str] = None
    parent: Optional[str] = None  # parent symbol name (for methods)
    calls: list = field(default_factory=list)
    params: list = field(default_factory=list)
    reads: list = field(default_factory=list)   # data/attrs read by this symbol
    writes: list = field(default_factory=list)  # data/attrs written by this symbol


@dataclass
class ParsedTest:
    framework: str          # pytest | junit | playwright | jest | mocha | testng | unknown
    test_cases: list = field(default_factory=list)
    covers_hints: list = field(default_factory=list)  # raw module/symbol names this test imports


@dataclass
class ParsedTouchpoints:
    """Framework-level surface area discovered in one file.

    Each list contains plain dicts so the indexer can dump them to JSON
    without further translation.
    """
    routes:    list = field(default_factory=list)  # {method, path, handler, framework}
    configs:   list = field(default_factory=list)  # {name, default, line}
    db_models: list = field(default_factory=list)  # {name, table, line}
    events:    list = field(default_factory=list)  # {name, kind, line}


@dataclass
class ParsedFile:
    language: str
    package: Optional[str] = None
    imports_raw: list = field(default_factory=list)
    symbols: list = field(default_factory=list)  # list[ParsedSymbol]
    test: Optional[ParsedTest] = None
    loc: int = 0
    touchpoints: Optional[ParsedTouchpoints] = None


class LanguageAdapter:
    """Subclass and override. All methods should be cheap and side-effect-free."""

    name: str = "base"
    extensions: tuple = ()

    # ---- file selection ----
    def matches(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    # ---- parsing ----
    def parse_file(self, path: Path, content: str) -> ParsedFile:
        raise NotImplementedError

    # ---- test detection ----
    def is_test(self, path: Path) -> bool:
        return False

    # ---- import resolution ----
    def resolve_import(self, raw: str, from_file: Path, repo_root: Path,
                       known_files: Iterable[Path]) -> Optional[str]:
        """Return a repo-relative POSIX path for the raw import, or None.

        Default implementation: no resolution. Adapters should override.
        """
        return None

    # ---- external dependency files (pyproject, package.json, pom.xml...) ----
    def external_deps(self, repo_root: Path) -> list:
        """Return a list of declared external dependency identifiers."""
        return []
