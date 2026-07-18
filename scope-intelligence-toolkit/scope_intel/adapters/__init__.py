from .base import LanguageAdapter, ParsedFile, ParsedSymbol, ParsedTest, ParsedTouchpoints
from .python_adapter import PythonAdapter
from .java_adapter import JavaAdapter
from .javascript_adapter import JavaScriptAdapter
from .playwright_adapter import PlaywrightAdapter
from .web_asset_adapter import WebAssetAdapter


def default_adapters():
    # Order matters: PlaywrightAdapter wraps JS/TS spec files, must run before JavaScriptAdapter.
    return [
        PythonAdapter(),
        JavaAdapter(),
        WebAssetAdapter(),
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
    "WebAssetAdapter",
    "default_adapters",
]
