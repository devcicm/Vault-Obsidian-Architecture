"""Permite `python -m cli`."""

import sys

from .vault_cli import main

if __name__ == "__main__":
    sys.exit(main())
