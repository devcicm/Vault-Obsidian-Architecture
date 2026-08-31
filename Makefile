.PHONY: install test lint check bootstrap clean help

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

lint:
	ruff check scripts/
	ruff format --check scripts/

# `make check` es lo que ejecuta quien no ha leído AGENTS.md, así que tiene que
# decir lo mismo que el repo defiende. Hasta v40.19 corría tres tools y ninguna
# puerta: publicaba una idea de «esto está bien» siete pasos por debajo de la
# del estándar. Se pregunta al registro (vault_gate.PUERTAS), no se listan a
# mano — una puerta nueva entra aquí sola el día que entra en el registro.
check:
	python scripts/vault_gate.py --strict
	python scripts/vault_standard_upgrade.py --check
	python scripts/vault_reindex.py --check
	python scripts/vault_audit.py

bootstrap:
	python scripts/vault_init.py

clean:
	rm -rf .pytest_cache __pycache__ .coverage coverage.xml htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

help:
	@echo "Vault Obsidian Architecture — Make targets:"
	@echo "  install     pip install -e '.[dev]' (editable install)"
	@echo "  test        run pytest (tests/)"
	@echo "  lint        ruff check + format check"
	@echo "  check       puertas del estándar + standard-upgrade + reindex + audit"
	@echo "  bootstrap   python scripts/vault_init.py (1-command vault init)"
	@echo "  clean       remove cache files"
