"""Python adapter — uses the stdlib `ast` module. Zero external deps."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Iterable, Optional

from .base import LanguageAdapter, ParsedFile, ParsedSymbol, ParsedTest, ParsedTouchpoints


# Decorator-based route detection covers Flask, FastAPI, Sanic, Bottle.
ROUTE_DECO_RE = re.compile(
    r'@(\w+)\.(get|post|put|delete|patch|route)\(\s*["\']([^"\']+)["\']'
    r'(?:[^)]*?methods\s*=\s*\[?\s*["\']([A-Z]+)["\'])?',
    re.M,
)
ENV_GET_RE = re.compile(
    r'os\.environ(?:\.get\(\s*["\']([A-Z_][A-Z0-9_]*)["\']'
    r'(?:\s*,\s*([^)]+?))?\s*\)|\[\s*["\']([A-Z_][A-Z0-9_]*)["\']\s*\])'
)
TABLENAME_RE = re.compile(r'__tablename__\s*=\s*["\']([^"\']+)["\']')
SQLA_MODEL_RE = re.compile(
    r'class\s+(\w+)\s*\([^)]*\b(?:Base|Model|db\.Model|DeclarativeBase)\b'
)


class PythonAdapter(LanguageAdapter):
    name = "python"
    extensions = (".py",)

    def is_test(self, path: Path) -> bool:
        n = path.name
        return n.startswith("test_") or n.endswith("_test.py") or "tests" in path.parts

    def parse_file(self, path: Path, content: str) -> ParsedFile:
        loc = content.count("\n") + 1
        try:
            tree = ast.parse(content, filename=str(path))
        except SyntaxError:
            return ParsedFile(language=self.name, loc=loc)

        symbols: list = []
        imports_raw: list = []
        package = self._infer_package(path)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports_raw.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                # preserve relative-import dots so resolver can use them
                prefix = "." * (node.level or 0)
                imports_raw.append(prefix + module)

        for node in tree.body:
            self._walk_top(node, symbols, parent=None, source_lines=content.splitlines())

        test: Optional[ParsedTest] = None
        if self.is_test(path):
            cases = [s.name for s in symbols if s.name.startswith("test_") and s.kind in ("function", "method")]
            test = ParsedTest(framework="pytest", test_cases=cases,
                              covers_hints=imports_raw[:])

        return ParsedFile(
            language=self.name,
            package=package,
            imports_raw=imports_raw,
            symbols=symbols,
            test=test,
            loc=loc,
            touchpoints=self._extract_touchpoints(content, symbols),
        )

    @staticmethod
    def _extract_touchpoints(content: str, symbols: list) -> ParsedTouchpoints:
        tp = ParsedTouchpoints()
        # routes — link decorator line to the next def
        symbol_lines = sorted([(s.line, s) for s in symbols if s.kind in ("function", "method")])
        for m in ROUTE_DECO_RE.finditer(content):
            framework = "flask"  # heuristic; covers most decorator styles
            method = (m.group(4) or m.group(2)).upper()
            if method == "ROUTE":
                method = "GET"
            path = m.group(3)
            line = content[:m.start()].count("\n") + 1
            handler = next((s.qualified_name or s.name
                            for ln, s in symbol_lines if ln >= line), None)
            tp.routes.append({
                "method": method, "path": path, "handler": handler,
                "framework": framework, "line": line,
            })
        for m in ENV_GET_RE.finditer(content):
            name = m.group(1) or m.group(3)
            default = (m.group(2) or "").strip() if m.group(1) else None
            tp.configs.append({
                "name": name, "default": default,
                "line": content[:m.start()].count("\n") + 1,
            })
        for m in SQLA_MODEL_RE.finditer(content):
            cls = m.group(1)
            line = content[:m.start()].count("\n") + 1
            # find a __tablename__ within next ~30 lines
            window = content[m.end(): m.end() + 1500]
            tn = TABLENAME_RE.search(window)
            tp.db_models.append({
                "name": cls, "table": tn.group(1) if tn else None, "line": line,
            })
        return tp

    def _walk_top(self, node, symbols: list, parent: Optional[str],
                  source_lines: Optional[list] = None) -> None:
        if isinstance(node, ast.ClassDef):
            sym = ParsedSymbol(
                name=node.name, kind="class", line=node.lineno,
                qualified_name=f"{parent}.{node.name}" if parent else node.name,
                parent=parent,
            )
            symbols.append(sym)
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    reads, writes = self._collect_data_flow(child)
                    method = ParsedSymbol(
                        name=child.name, kind="method", line=child.lineno,
                        qualified_name=f"{sym.qualified_name}.{child.name}",
                        parent=sym.qualified_name,
                        params=[a.arg for a in child.args.args],
                        calls=self._collect_calls(child),
                        reads=reads,
                        writes=writes,
                    )
                    symbols.append(method)
                elif isinstance(child, ast.ClassDef):
                    self._walk_top(child, symbols, parent=sym.qualified_name,
                                   source_lines=source_lines)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            reads, writes = self._collect_data_flow(node)
            symbols.append(ParsedSymbol(
                name=node.name, kind="function", line=node.lineno,
                qualified_name=node.name, parent=parent,
                params=[a.arg for a in node.args.args],
                calls=self._collect_calls(node),
                reads=reads,
                writes=writes,
            ))

    @staticmethod
    def _collect_data_flow(func_node) -> tuple:
        """Return (reads, writes) for a function/method node.

        Tracks self.attr / cls.attr accesses:
          - left-hand side of assignment → write
          - any other attribute access    → read
        Also tracks top-level name loads that look like global state.
        Capped at 30 each to stay compact.
        """
        writes: list = []
        reads: list = []
        seen_w: set = set()
        seen_r: set = set()

        def _attr_str(node) -> Optional[str]:
            parts = []
            cur = node
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
                return ".".join(reversed(parts))
            return None

        for n in ast.walk(func_node):
            if isinstance(n, ast.Assign):
                for target in n.targets:
                    if isinstance(target, ast.Attribute):
                        s = _attr_str(target)
                        if s and s not in seen_w:
                            seen_w.add(s)
                            writes.append(s)
            elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Attribute):
                s = _attr_str(n.target)
                if s and s not in seen_w:
                    seen_w.add(s)
                    writes.append(s)
            elif isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load):
                s = _attr_str(n)
                if s and s not in seen_r and s not in seen_w:
                    seen_r.add(s)
                    reads.append(s)

        return reads[:30], writes[:30]

    @staticmethod
    def _collect_calls(func_node) -> list:
        out: list = []
        for n in ast.walk(func_node):
            if isinstance(n, ast.Call):
                target = n.func
                if isinstance(target, ast.Name):
                    out.append(target.id)
                elif isinstance(target, ast.Attribute):
                    parts: list = []
                    cur = target
                    while isinstance(cur, ast.Attribute):
                        parts.append(cur.attr)
                        cur = cur.value
                    if isinstance(cur, ast.Name):
                        parts.append(cur.id)
                    out.append(".".join(reversed(parts)))
        # de-dupe while preserving order
        seen, dedup = set(), []
        for c in out:
            if c not in seen:
                seen.add(c)
                dedup.append(c)
        return dedup[:50]

    @staticmethod
    def _infer_package(path: Path) -> Optional[str]:
        parts = list(path.with_suffix("").parts)
        # drop common root dirs
        while parts and parts[0] in ("src", "lib", "app", "."):
            parts = parts[1:]
        if not parts:
            return None
        return ".".join(parts[:-1]) or None

    def resolve_import(self, raw: str, from_file: Path, repo_root: Path,
                       known_files: Iterable[Path]) -> Optional[str]:
        if not raw:
            return None
        known_set = {p.as_posix() for p in known_files}

        # Relative import: leading dots
        if raw.startswith("."):
            level = len(raw) - len(raw.lstrip("."))
            mod = raw.lstrip(".")
            base = from_file.parent
            for _ in range(level - 1):
                base = base.parent
            candidate_parts = mod.split(".") if mod else []
        else:
            base = repo_root
            candidate_parts = raw.split(".")

        if not candidate_parts:
            return None

        # try as <parts>.py and <parts>/__init__.py
        rel_path = base.joinpath(*candidate_parts)
        for cand in (rel_path.with_suffix(".py"),
                     rel_path / "__init__.py"):
            try:
                rel = cand.resolve().relative_to(repo_root.resolve()).as_posix()
            except (ValueError, OSError):
                continue
            if rel in known_set:
                return rel

        # absolute import — try with common src prefixes
        for prefix in ("src", "lib", "app"):
            rel_path2 = repo_root / prefix / Path(*candidate_parts)
            for cand in (rel_path2.with_suffix(".py"),
                         rel_path2 / "__init__.py"):
                try:
                    rel = cand.resolve().relative_to(repo_root.resolve()).as_posix()
                except (ValueError, OSError):
                    continue
                if rel in known_set:
                    return rel

        # fallback: search by basename
        leaf = candidate_parts[-1] + ".py"
        for p in known_set:
            if p.endswith("/" + leaf) or p == leaf:
                return p
        return None

    def external_deps(self, repo_root: Path) -> list:
        deps: list = []
        # requirements.txt
        req = repo_root / "requirements.txt"
        if req.exists():
            try:
                for line in req.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    deps.append(line)
            except OSError:
                pass
        # pyproject.toml — naive scan, no toml dep needed
        pyproj = repo_root / "pyproject.toml"
        if pyproj.exists():
            try:
                txt = pyproj.read_text(encoding="utf-8", errors="ignore")
                for m in re.finditer(r'^\s*"([A-Za-z0-9_.\-]+)\s*[<>=!~]', txt, re.M):
                    deps.append(m.group(1))
            except OSError:
                pass
        # de-dupe
        seen, out = set(), []
        for d in deps:
            key = d.split("==")[0].split(">=")[0].split("<=")[0].strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append(d)
        return out
