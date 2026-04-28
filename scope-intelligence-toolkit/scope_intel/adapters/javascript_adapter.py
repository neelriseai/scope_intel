"""JavaScript / TypeScript adapter — regex-based."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Optional

from .base import LanguageAdapter, ParsedFile, ParsedSymbol, ParsedTest, ParsedTouchpoints


# Express / Koa / Fastify-style routes: app.get("/path", ...)
EXPRESS_ROUTE_RE = re.compile(
    r'\b(\w+)\.(get|post|put|delete|patch|use|all)\s*\(\s*["\'`]([^"\'`]+)["\'`]'
)
PROCESS_ENV_RE = re.compile(
    r'process\.env(?:\.([A-Z_][A-Z0-9_]*)|\[\s*["\']([A-Z_][A-Z0-9_]*)["\']\s*\])'
)
IMPORT_META_ENV_RE = re.compile(r'import\.meta\.env\.([A-Z_][A-Z0-9_]*)')


IMPORT_RE = re.compile(
    r'(?:import\s+(?:[\w*\s{},]+\s+from\s+)?["\']([^"\']+)["\'])'
    r'|(?:require\(\s*["\']([^"\']+)["\']\s*\))'
)
EXPORT_FN_RE = re.compile(
    r'^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)',
    re.M,
)
ARROW_FN_RE = re.compile(
    r'^\s*(?:export\s+(?:default\s+)?)?const\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>',
    re.M,
)
CLASS_RE = re.compile(r'^\s*(?:export\s+(?:default\s+)?)?class\s+(\w+)', re.M)
METHOD_RE = re.compile(r'^\s+(?:async\s+|static\s+|public\s+|private\s+|protected\s+)*(\w+)\s*\(([^)]*)\)\s*\{', re.M)

TEST_BLOCK_RE = re.compile(r'\b(?:test|it)\s*\(\s*["\'`]([^"\'`]+)["\'`]')


class JavaScriptAdapter(LanguageAdapter):
    name = "javascript"
    extensions = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")

    def is_test(self, path: Path) -> bool:
        n = path.name.lower()
        return (
            n.endswith(".test.js") or n.endswith(".test.ts")
            or n.endswith(".spec.js") or n.endswith(".spec.ts")
            or n.endswith(".test.jsx") or n.endswith(".test.tsx")
            or n.endswith(".spec.jsx") or n.endswith(".spec.tsx")
            or "__tests__" in path.parts
        )

    def parse_file(self, path: Path, content: str) -> ParsedFile:
        loc = content.count("\n") + 1
        cleaned = _strip_js_comments(content)

        imports_raw: list = []
        for m in IMPORT_RE.finditer(cleaned):
            imports_raw.append(m.group(1) or m.group(2))

        symbols: list = []
        for m in CLASS_RE.finditer(cleaned):
            symbols.append(ParsedSymbol(
                name=m.group(1), kind="class",
                line=cleaned[:m.start()].count("\n") + 1,
                qualified_name=m.group(1),
            ))
        for m in EXPORT_FN_RE.finditer(cleaned):
            params = [p.strip().split(":")[0].split("=")[0].strip()
                      for p in m.group(2).split(",") if p.strip()]
            symbols.append(ParsedSymbol(
                name=m.group(1), kind="function",
                line=cleaned[:m.start()].count("\n") + 1,
                qualified_name=m.group(1),
                params=params,
            ))
        for m in ARROW_FN_RE.finditer(cleaned):
            params = [p.strip().split(":")[0].split("=")[0].strip()
                      for p in m.group(2).split(",") if p.strip()]
            symbols.append(ParsedSymbol(
                name=m.group(1), kind="function",
                line=cleaned[:m.start()].count("\n") + 1,
                qualified_name=m.group(1),
                params=params,
            ))

        test: Optional[ParsedTest] = None
        if self.is_test(path):
            cases = [m.group(1) for m in TEST_BLOCK_RE.finditer(cleaned)]
            framework = "jest"
            test = ParsedTest(framework=framework, test_cases=cases,
                              covers_hints=imports_raw[:])

        return ParsedFile(
            language=self.name,
            package=None,
            imports_raw=imports_raw,
            symbols=symbols,
            test=test,
            loc=loc,
            touchpoints=self._extract_touchpoints(cleaned),
        )

    @staticmethod
    def _extract_touchpoints(cleaned: str) -> ParsedTouchpoints:
        tp = ParsedTouchpoints()
        for m in EXPRESS_ROUTE_RE.finditer(cleaned):
            verb = m.group(2).upper()
            tp.routes.append({
                "method": verb if verb != "USE" else "MIDDLEWARE",
                "path": m.group(3),
                "handler": None,
                "framework": "express",
                "line": cleaned[:m.start()].count("\n") + 1,
            })
        seen: set = set()
        for m in PROCESS_ENV_RE.finditer(cleaned):
            name = m.group(1) or m.group(2)
            if name in seen:
                continue
            seen.add(name)
            tp.configs.append({
                "name": name, "default": None,
                "line": cleaned[:m.start()].count("\n") + 1,
            })
        for m in IMPORT_META_ENV_RE.finditer(cleaned):
            name = m.group(1)
            if name in seen:
                continue
            seen.add(name)
            tp.configs.append({
                "name": name, "default": None,
                "line": cleaned[:m.start()].count("\n") + 1,
            })
        return tp

    def resolve_import(self, raw: str, from_file: Path, repo_root: Path,
                       known_files: Iterable[Path]) -> Optional[str]:
        if not raw or not raw.startswith((".", "/")):
            return None  # bare specifier => external module
        known_set = {p.as_posix() for p in known_files}
        base = from_file.parent if raw.startswith(".") else repo_root
        target = (base / raw).resolve()
        try:
            rel = target.relative_to(repo_root.resolve())
        except ValueError:
            return None
        rel_posix = rel.as_posix()

        # exact, with extensions, or as folder index
        candidates = [rel_posix]
        for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
            candidates.append(rel_posix + ext)
        for ext in ("/index.ts", "/index.tsx", "/index.js", "/index.jsx"):
            candidates.append(rel_posix + ext)

        for c in candidates:
            if c in known_set:
                return c
        return None

    def external_deps(self, repo_root: Path) -> list:
        pkg = repo_root / "package.json"
        if not pkg.exists():
            return []
        try:
            data = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, ValueError):
            return []
        out: list = []
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            for name, ver in (data.get(key) or {}).items():
                out.append(f"{name}@{ver}")
        return out


def _strip_js_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), src, flags=re.S)
    src = re.sub(r"//[^\n]*", "", src)
    return src
