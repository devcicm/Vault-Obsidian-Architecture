"""Adaptador generado para la operación canónica ``vault_requirement_save``."""

from vault_toolkit.loading import import_toolkit_module, legacy_scripts_for

_impl = import_toolkit_module(
    "vault_requirement_save",
    legacy_scripts=legacy_scripts_for(__file__),
)
main = _impl.main


def __getattr__(name):
    return getattr(_impl, name)


if __name__ == "__main__":
    import sys

    wrap_main = import_toolkit_module(
        "vault_errors",
        legacy_scripts=legacy_scripts_for(__file__),
    ).wrap_main
    sys.exit(wrap_main(main, "vault_requirement_save"))
