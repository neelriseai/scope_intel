from .base import LanguageAdapter, ParsedFile, ParsedSymbol, ParsedTest, ParsedTouchpoints
from .python_adapter import PythonAdapter
from .java_adapter import JavaAdapter
from .javascript_adapter import JavaScriptAdapter
from .playwright_adapter import PlaywrightAdapter


def default_adapters():
    # Order matters: PlaywrightAdapter wraps JS/TS spec files, must run before JavaScriptAdapter.
    return [
        PythonAdapter(),
        JavaAdapter(),
        PlaywrightAdapter(),
        JavaScriptAdapter(),
    ]


__all__ = [
    "LanguageAdapter",
    "ParsedFile",
    "ParsedSymbol",
    "ParsedTest",
    "ParsedTouchpoints",
    "PythonAdapter",
    "JavaAdapter",
    "JavaScriptAdapter",
    "PlaywrightAdapter",
    "default_adapters",
]
