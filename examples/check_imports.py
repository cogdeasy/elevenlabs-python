"""CI smoke check: import every example module to verify it is runnable.

Sets a dummy API key so module-level environment access succeeds.  No
network calls are made — examples only reach the API inside main()/handlers.
"""

import importlib.util
import os
import pathlib
import sys

os.environ.setdefault("ELEVENLABS_API_KEY", "sk-dummy-key-for-import-check")

EXAMPLES_DIR = pathlib.Path(__file__).parent


def main() -> int:
    failures = []
    for path in sorted(EXAMPLES_DIR.glob("*.py")):
        if path.name == "check_imports.py":
            continue
        spec = importlib.util.spec_from_file_location(f"examples.{path.stem}", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            print(f"OK   {path.name}")
        except Exception as e:
            failures.append((path.name, e))
            print(f"FAIL {path.name}: {e}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
