"""AP-70: entrada canonica de politica de mutacion invalida."""

NORMA = {
    "code": "AP-70",
    "name": "Politica de mutacion ilegible o invalida",
    "type": "antipattern",
    "category": "structure",
    "severity": "critical",
    "enforcement": "guard+audit",
    "description": "Una politica de mutacion existente invalida o ilegible no puede tratarse como ausencia de restricciones.",
    "signal": "Un archivo de politica existente contiene JSON, claves o valores invalidos o no se puede leer.",
    "prevention": "Detener las mutaciones gobernadas, informar al propietario y conservar el archivo; una politica ausente sigue sin imponer reglas.",
    "tools_enforcing": ["vault_io", "vault_write", "vault_delete", "vault_move"],
    "tools_detecting": ["vault_norms"],
    "distinguido_de": {"AP-36": "AP-36 contiene rutas de efectos; AP-70 trata interpretacion de politica."},
    "introduced_version": "v41.26",
    "revisado_en": "2026-11-10",
}
