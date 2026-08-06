"""Dominio del estándar, organizado en contextos acotados.

`scripts/` sigue siendo la superficie publicada —el tool-spec, `cli/registry.py`
y el runner del MCP resuelven por esa ruta y no se toca ni un fichero de allí—.
Este paquete es a dónde se muda la decisión: los adaptadores parsean argv y
emiten el envelope, el dominio decide.

El plano vive en `scripts/vault_arch.py` (`CONTEXTS`) y se deriva a
`docs/ARQUITECTURA.md`.
"""
