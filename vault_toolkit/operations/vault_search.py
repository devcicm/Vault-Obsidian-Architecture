"""Adaptador generado para la operación canónica ``vault_search``."""

from vault_toolkit.loading import import_toolkit_module, legacy_scripts_for

_impl = import_toolkit_module(
    "vault_search",
    legacy_scripts=legacy_scripts_for(__file__),
)
main = _impl.main


def __getattr__(name):
    return getattr(_impl, name)


if __name__ == "__main__":
    import sys
    _errores = import_toolkit_module(
        "vault_errors",
        legacy_scripts=legacy_scripts_for(__file__),
    )
    sys.exit(_errores.wrap_main(main, "vault_search"))
