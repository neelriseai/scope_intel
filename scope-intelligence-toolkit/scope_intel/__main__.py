import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-16"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
