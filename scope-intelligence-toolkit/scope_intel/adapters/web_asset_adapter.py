"""Adapter for HTML and CSS dependency edges without storing source content."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import unquote, urlsplit

from .base import LanguageAdapter, ParsedFile


CSS_IMPORT_RE = re.compile(
    r"""@import\s+(?:url\(\s*)?["']?([^"')\s;]+)""",
    re.IGNORECASE,
)
CSS_URL_RE = re.compile(r"""url\(\s*["']?([^"')]+)["']?\s*\)""", re.IGNORECASE)


class _HtmlDependencyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.dependencies: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        values = {str(name).lower(): value for name, value in attrs}
        dependency = ""
        if tag.lower() == "script":
            dependency = str(values.get("src") or "")
        elif tag.lower() == "link":
            rel = {part.lower() for part in str(values.get("rel") or "").split()}
            if rel.intersection({"stylesheet", "modulepreload", "preload"}):
                dependency = str(values.get("href") or "")
        if dependency:
            self.dependencies.append(dependency)


class WebAssetAdapter(LanguageAdapter):
    """Index static web files and resolve their local script/style dependencies."""

    name = "web_asset"
    extensions = (".html", ".htm", ".css")

    def parse_file(self, path: Path, content: str) -> ParsedFile:
        suffix = path.suffix.lower()
        if suffix in (".html", ".htm"):
            parser = _HtmlDependencyParser()
            try:
                parser.feed(content)
            except Exception:  # HTMLParser is best-effort for incomplete templates.
                pass
            imports_raw = parser.dependencies
            language = "html"
        else:
            imports_raw = [
                *CSS_IMPORT_RE.findall(content),
                *CSS_URL_RE.findall(content),
            ]
            language = "css"
        return ParsedFile(
            language=language,
            package=path.parent.name or None,
            imports_raw=list(dict.fromkeys(imports_raw)),
            loc=content.count("\n") + 1,
        )

    def resolve_import(
        self,
        raw: str,
        from_file: Path,
        repo_root: Path,
        known_files: Iterable[Path],
    ) -> Optional[str]:
        value = unquote(str(raw or "").strip())
        if not value or value.startswith(("#", "data:", "blob:", "javascript:")):
            return None
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc or not parsed.path:
            return None
        relative_path = parsed.path.replace("\\", "/")
        if relative_path.startswith("/"):
            candidate = repo_root / relative_path.lstrip("/")
        else:
            candidate = from_file.parent / relative_path
        try:
            rel = candidate.resolve().relative_to(repo_root.resolve()).as_posix()
        except (OSError, ValueError):
            return None
        known = {path.as_posix() for path in known_files}
        return rel if rel in known else None

