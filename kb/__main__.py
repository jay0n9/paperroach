"""Allow `python -m kb ...` as an alias for the `kb` console script."""
from kb.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
