#!/usr/bin/env python3
"""Gate de producto del lifecycle; reutiliza el aislamiento del clean install."""

from clean_install_gate import main


if __name__ == "__main__":
    raise SystemExit(main(gate="RUNTIME_LIFECYCLE_GATE"))
