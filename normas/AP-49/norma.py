"""AP-49 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-49",
    "name": "Vínculo resuelto en tiempo de import",
    "type": "antipattern",
    "category": "architecture",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "Un módulo deriva su ruta, su configuración o su dependencia en el "
        "momento de **importarse**, no en el de usarse. `SYSTEM_DIR = "
        "VAULT_ROOT / '00_System'` a nivel de módulo se evalúa una sola vez, "
        "cuando el intérprete carga el fichero, y a partir de ahí es una "
        "constante.\n\n"
        "Lo grave no es la constante: es que deja **inerte una costura que "
        "existe**. `vault_io.set_vault_root()` está publicado y 12 tests lo "
        "usan, pero no puede reapuntar a un módulo que ya calculó su ruta al "
        "cargar. La inyección parece disponible y no lo está, que es peor que "
        "no tenerla — quien la usa cree haber redirigido la escritura.\n\n"
        "Medido en v40.0 por el propio guard: **0 vínculos congelados en "
        "0 módulos**. "
        "Eran 82 en 62 módulos antes de empezar a migrar contextos al "
        "dominio, y cayeron uno a uno: Durabilidad los dejó en 77, "
        "Índices en 69, Grafo en 51, Consulta en 45, Gobernanza en 38, "
        "Ciclo de vida en 34, Meta-toolkit en 31 y Autoría —donde estaban "
        "los 31 últimos, el 100% de la deuda que quedaba— en 0. Llegar a "
        "cero destapó la otra mitad de la norma: veinte módulos seguían "
        "haciendo `from vault_io import VAULT_ROOT` y usándolo **dentro de "
        "funciones**. No son asignaciones de nivel de módulo, así que el "
        "guard los daba por limpios, y seguían dependiendo del paliativo de "
        "reanclaje que el refactor existe para no necesitar. Se mide aparte "
        "(`raw_vault_root_imports`), también en cero, y el caso legítimo se "
        "pide con alias. La "
        "cifra es la que "
        "cuenta `vault_arch --check`, no una estimación a ojo: la norma y su "
        "puerta miden lo mismo o la norma no es comprobable. La consecuencia visible era "
        "que `cli/runner.py` aislaba cada tool en un subproceso citando "
        "«estado a nivel de módulo» como razón: el aislamiento por proceso "
        "no era una decisión de diseño libre sino la compensación de este "
        "acoplamiento. Saldada la deuda, esa razón caducó y quedó anotada "
        "allí mismo; el subproceso se conserva por las otras dos que siguen "
        "siendo ciertas —timeout que puede matar lo que vigila, y envelope "
        "sin reinterpretar—. El refactor lo hizo posible, no conveniente."
    ),
    "signal": (
        "Las pruebas necesitan subprocesos para aislarse unas de otras; "
        "`set_vault_root()` no cambia dónde escribe una tool; dos raíces de "
        "vault no pueden coexistir en el mismo intérprete; una asignación de "
        "nivel de módulo deriva de `VAULT_ROOT` sin pasar por "
        "`get_vault_root()`."
    ),
    "prevention": (
        "La raíz y sus derivadas se reciben, no se importan: el dominio toma "
        "un contexto (`VaultContext`) y el adaptador lo construye por "
        "llamada. Si un módulo necesita la ruta, la resuelve **tarde** con "
        "`get_vault_root()` dentro de la función. El guard es AST sobre "
        "asignaciones de nivel de módulo que derivan de `VAULT_ROOT`, con "
        "baseline que solo puede encoger — la deuda medida no se arregla en "
        "un commit, pero no puede crecer."
    ),
    "tools_enforcing": ["vault_arch"],
    "tools_detecting": ["vault_norms", "vault_arch"],
    "distinguido_de": {
        "AP-58": (
            "AP-49 mira **cuándo** se resuelve un vínculo: un valor "
            "copiado en tiempo de import deja de responder a un reanclaje. "
            "AP-58 mira la **dirección** de la dependencia, no su momento. "
            "Se tocan porque el ciclo del núcleo es parte de lo que obliga "
            "a congelar vínculos, pero un módulo puede tener ciclos sin un "
            "solo vínculo congelado, y al revés."
        )
    },
    "introduced_version": "v40.0",
}
