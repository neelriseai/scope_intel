"""Java adapter — regex-based, no JVM or tree-sitter required."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Optional

from .base import LanguageAdapter, ParsedFile, ParsedSymbol, ParsedTest, ParsedTouchpoints


# Spring MVC route detection
SPRING_ROUTE_RE = re.compile(
    r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)'
    r'\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']'
    r'(?:[^)]*?method\s*=\s*RequestMethod\.([A-Z]+))?'
)
SPRING_VALUE_RE = re.compile(r'@Value\s*\(\s*["\']\$\{([^:}]+)(?::([^}]*))?\}["\']\s*\)')
JPA_ENTITY_RE = re.compile(r'@Entity[^@\n]*?\s*(?:@Table\s*\(\s*name\s*=\s*["\']([^"\']+)["\'])?', re.S)


PACKAGE_RE = re.compile(r'^\s*package\s+([\w.]+)\s*;', re.M)
IMPORT_RE = re.compile(r'^\s*import\s+(?:static\s+)?([\w.\*]+)\s*;', re.M)
TYPE_RE = re.compile(
    r'^\s*(?:public|private|protected|abstract|final|static|sealed|\s)*'
    r'(class|interface|enum|record)\s+(\w+)',
    re.M,
)
METHOD_RE = re.compile(
    r'^[ \t]*(?:public|private|protected|static|final|abstract|synchronized|default|\s)+'
    r'(?:<[^>]+>\s+)?'                  # generic type params
    r'(?:[\w<>\[\],\s.?]+?)\s+'         # return type
    r'(\w+)\s*\(([^)]*)\)\s*'           # name + params
    r'(?:throws\s+[\w.,\s]+)?\s*[\{;]',
    re.M,
)
TEST_ANNO_RE = re.compile(r'@(Test|ParameterizedTest)\b')
JUNIT_IMPORT = re.compile(r'org\.junit')
TESTNG_IMPORT = re.compile(r'org\.testng')


class JavaAdapter(LanguageAdapter):
    name = "java"
    extensions = (".java",)

    def is_test(self, path: Path) -> bool:
        if path.name.endswith("Test.java") or path.name.endswith("IT.java"):
            return True
        parts = {p.lower() for p in path.parts}
        return "test" in parts or "tests" in parts

    def parse_file(self, path: Path, content: str) -> ParsedFile:
        loc = content.count("\n") + 1
        # Strip block + line comments to avoid false matches
        cleaned = _strip_comments(content)

        package = None
        m = PACKAGE_RE.search(cleaned)
        if m:
            package = m.group(1)

        imports_raw = [m.group(1) for m in IMPORT_RE.finditer(cleaned)]

        symbols: list = []
        for tm in TYPE_RE.finditer(cleaned):
            kind = {"class": "class", "interface": "interface",
                    "enum": "enum", "record": "class"}[tm.group(1)]
            type_name = tm.group(2)
            qn = f"{package}.{type_name}" if package else type_name
            symbols.append(ParsedSymbol(
                name=type_name, kind=kind,
                line=cleaned[:tm.start()].count("\n") + 1,
                qualified_name=qn,
            ))

        # methods (best-effort; not nested-class aware)
        last_type = None
        for sym in symbols:
            if sym.kind in ("class", "interface", "enum"):
                last_type = sym.qualified_name
                break

        for mm in METHOD_RE.finditer(cleaned):
            name = mm.group(1)
            if name in ("if", "for", "while", "switch", "catch", "return", "new"):
                continue
            params_raw = mm.group(2).strip()
            params = [p.strip().split()[-1] for p in params_raw.split(",") if p.strip()]
            symbols.append(ParsedSymbol(
                name=name, kind="method",
                line=cleaned[:mm.start()].count("\n") + 1,
                qualified_name=f"{last_type}.{name}" if last_type else name,
                parent=last_type,
                params=params,
            ))

        test: Optional[ParsedTest] = None
        if self.is_test(path) or TEST_ANNO_RE.search(cleaned):
            framework = "junit" if JUNIT_IMPORT.search(cleaned) else (
                        "testng" if TESTNG_IMPORT.search(cleaned) else "junit")
            cases: list = []
            for am in TEST_ANNO_RE.finditer(cleaned):
                tail = cleaned[am.end():am.end() + 400]
                nm = METHOD_RE.search(tail)
                if nm:
                    cases.append(nm.group(1))
            test = ParsedTest(framework=framework, test_cases=cases,
                              covers_hints=imports_raw[:])

        return ParsedFile(
            language=self.name,
            package=package,
            imports_raw=imports_raw,
            symbols=symbols,
            test=test,
            loc=loc,
            touchpoints=self._extract_touchpoints(cleaned, symbols),
        )

    @staticmethod
    def _extract_touchpoints(cleaned: str, symbols: list) -> ParsedTouchpoints:
        tp = ParsedTouchpoints()
        method_lines = sorted([(s.line, s) for s in symbols if s.kind == "method"])
        for m in SPRING_ROUTE_RE.finditer(cleaned):
            anno = m.group(1)
            method = (m.group(3) or {
                "GetMapping": "GET", "PostMapping": "POST", "PutMapping": "PUT",
                "DeleteMapping": "DELETE", "PatchMapping": "PATCH",
                "RequestMapping": "GET",
            }[anno])
            line = cleaned[:m.start()].count("\n") + 1
            handler = next((s.qualified_name or s.name
                            for ln, s in method_lines if ln >= line), None)
            tp.routes.append({
                "method": method, "path": m.group(2), "handler": handler,
                "framework": "spring", "line": line,
            })
        for m in SPRING_VALUE_RE.finditer(cleaned):
            tp.configs.append({
                "name": m.group(1), "default": m.group(2),
                "line": cleaned[:m.start()].count("\n") + 1,
            })
        for m in JPA_ENTITY_RE.finditer(cleaned):
            line = cleaned[:m.start()].count("\n") + 1
            # try to bind @Entity to the class declared right after
            window = cleaned[m.end(): m.end() + 800]
            tm = re.search(r'class\s+(\w+)', window)
            if tm:
                tp.db_models.append({
                    "name": tm.group(1), "table": m.group(1), "line": line,
                })
        return tp

    def resolve_import(self, raw: str, from_file: Path, repo_root: Path,
                       known_files: Iterable[Path]) -> Optional[str]:
        if not raw or raw.endswith(".*"):
            # wildcard imports cannot be resolved precisely; skip
            return None
        target_class = raw.rsplit(".", 1)[-1]
        target_path_suffix = raw.replace(".", "/") + ".java"
        for p in known_files:
            posix = p.as_posix()
            if posix.endswith("/" + target_path_suffix) or posix == target_path_suffix:
                return posix
            # fallback by class name
            if posix.endswith("/" + target_class + ".java"):
                return posix
        return None

    def external_deps(self, repo_root: Path) -> list:
        deps: list = []
        pom = repo_root / "pom.xml"
        if pom.exists():
            try:
                txt = pom.read_text(encoding="utf-8", errors="ignore")
                for m in re.finditer(
                    r"<dependency>\s*<groupId>([^<]+)</groupId>\s*<artifactId>([^<]+)</artifactId>",
                    txt,
                ):
                    deps.append(f"{m.group(1)}:{m.group(2)}")
            except OSError:
                pass
        for gradle_name in ("build.gradle", "build.gradle.kts"):
            gp = repo_root / gradle_name
            if gp.exists():
                try:
                    txt = gp.read_text(encoding="utf-8", errors="ignore")
                    for m in re.finditer(
                        r'(?:implementation|api|testImplementation|compileOnly|runtimeOnly)'
                        r'[\s(]+["\']([^"\']+)["\']',
                        txt,
                    ):
                        deps.append(m.group(1))
                except OSError:
                    pass
        # de-dupe
        seen, out = set(), []
        for d in deps:
            if d not in seen:
                seen.add(d)
                out.append(d)
        return out


def _strip_comments(src: str) -> str:
    # remove /* ... */ and // ... — keep newlines so line numbers stay roughly correct
    src = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), src, flags=re.S)
    src = re.sub(r"//[^\n]*", "", src)
    return src
