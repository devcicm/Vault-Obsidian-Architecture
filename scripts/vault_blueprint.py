#!/usr/bin/env python3
"""vault_blueprint — el plano de construcción: qué se construye, sobre qué, y con qué guard.

Este repo tenía once registros canónicos —`SERVICIO`, `CAPACIDADES`, `CONTEXTS`,
`NORM_CATALOG`, `FUNDAMENTALS`, `GROUPS`/`TOOLS_CATALOG`, `VOCABULARIOS`, `PUERTAS`,
`STATUS_VOCAB`, `LIFECYCLE_REGISTRY` y el `tool-spec.json`— repartidos en diez módulos
y **sin nada que los atase**. Se podía responder cualquier pregunta dentro de un
registro y ninguna que cruzara dos: «esta tool, ¿a qué servicio sirve?», «esta norma,
¿qué puerta la hace cumplir y qué test la muerde?». `docs/ARQUITECTURA.md` cubre una
sola capa —contextos y puertos— y no pretende otra cosa.

    python scripts/vault_blueprint.py --blueprint      # regenera docs/BLUEPRINT.md
    python scripts/vault_blueprint.py --check --strict # el doc vs. los registros
    python scripts/vault_blueprint.py --freeze         # capa 4: congela la deuda

## El papelito manda porque el código lo escribe

La petición era «papelito manda, fuente de verdad única»; `AGENTS.md` regla 3 dice
«registro canónico primero, doc después», y añade que documentar sin código ejecutable
«es el fallo histórico que el estándar ya cometió una vez». Las dos cosas se cumplen de
la única forma que no se pudre: **el plano manda porque lo genera el código y una
puerta falla si diverge.** Ni una cifra de este documento se escribe a mano — incluida
la deuda declarada, que vive en el registro `DEUDA_DECLARADA` de este módulo y no en la
prosa del doc. Un plano editable a mano sería, exactamente, el fallo que describe.

## Por qué solo la capa 4 tiene baseline

Las capas 1, 2, 3, 5 y 6 se miden en cero el día que se declaran: sus datos ya existían
y solo faltaba atarlos. La capa 4 no: al cruzar `NORM_CATALOG` con `PUERTAS` y con
`tests/` por primera vez aparecieron 16 normas sin puerta **ni** test. Exigir cero el
primer día habría hecho nacer la puerta en rojo, y una puerta en rojo se desactiva —
esa lección ya se pagó aquí. Baseline indexada por código de norma, que solo encoge.

## Lo que esta tool NO hace

**No reimplementa ningún guard.** Los puertos rotos los dice `vault_arch.puertos_rotos()`,
los contratos `vault_mcp_catalog.check_contracts()` y la trazabilidad del servicio
`vault_servicio.check()`. Si mirara los datos por su cuenta sería una segunda fuente de
verdad sobre el repo (AP-05) midiendo con criterio propio (AP-44) — que es justo lo que
un plano no puede permitirse.
"""

import argparse
import ast
import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

import vault_baseline
from vault_errors import emit_error, wrap_main

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
DOC = REPO_ROOT / "docs" / "BLUEPRINT.md"
BASELINE = SCRIPTS_DIR / "blueprint-baseline.json"
TESTS_DIR = REPO_ROOT / "tests"


#: Estados admitidos de una deuda declarada. `pendiente` es el único que la deja
#: viva; `saldada` la conserva con la versión que la cerró, porque una deuda que
#: desaparece del registro no se distingue de una que nadie volvió a mirar.
#: No hay `en_curso`: o está saldada y se puede citar la versión, o está
#: pendiente — un estado intermedio sería una promesa, y una promesa no es un
#: dato verificable (AP-37).
ESTADOS_DE_DEUDA = ("pendiente", "saldada")

#: Deuda conocida que **no** se ataca en esta tanda, con el motivo por el que no.
#: Vive aquí y no en la prosa del plano por la misma razón que todo lo demás: una
#: lista de deuda escrita a mano en un documento derivado se queda quieta el día
#: que la deuda se salda, y entonces el plano miente en la dirección cómoda.
#:
#: `estado` y `desde` son obligatorios desde v40.11, y son el mismo argumento
#: llevado un paso más: hasta entonces la lista solo tenía deuda viva, así que
#: «pendiente» era una propiedad implícita de estar en ella. Implícita significa
#: que nadie la comprueba — y el día que una entrada se saldara, la forma natural
#: de anotarlo habría sido borrarla, que es exactamente cómo un registro de deuda
#: deja de servir para nada.
DEUDA_DECLARADA: List[Dict[str, Any]] = [
    {
        "id": "envelopes_del_dominio_sin_error_code",
        "estado": "saldada",
        "saldada_en": "v40.29",
        "sostenida_por": [
            "tests/test_ap52_contrato_de_error.py::test_la_deuda_de_ap52_esta_saldada",
        ],
        "desde": "v40.9",
        "capa": "5",
        "que": (
            "Nueve `{\"ok\": False, \"error\": ...}` en `vault/durabilidad/` y "
            "`vault/indices/` que los adaptadores de `scripts/` devuelven tal cual "
            "al consumidor: el envelope sale sin `error_code` ni `recovery`. "
            "Aparecieron en v40.9 al ensanchar el alcance de AP-52 más allá de "
            "`scripts/`, y quedan congelados en `error-contract-baseline.json`. "
            "v40.29 los saldó partiendo la frase en dos mitades con dueño: el "
            "dominio levanta un `FalloDeDominio` que nombra la **causa** "
            "(`vault/kernel/fallos.py`, sin un solo import fuera de `typing`) y "
            "la traducción a `error_code` vive en un único sitio del lado de la "
            "herramienta, `vault_errors.emit_fallo`. Se levanta en vez de "
            "devolver porque un fallo devuelto como valor se ignora por olvido, "
            "y uno de los cuatro casos es el borrado del vault sin confirmar. "
            "La baseline de AP-52 queda **vacía por primera vez desde que la "
            "norma existe**, y los campos que el contrato declara estables "
            "—`error`, `hint`, `searched`— siguen saliendo: mejorar el envelope "
            "por debajo no autoriza a romper el contrato de arriba."
        ),
        "por_que_no_ahora": (
            "La pregunta de fondo no es cómo se escribe el envelope sino quién lo "
            "escribe: hacer que el dominio importe `vault_errors` lo ata al "
            "catálogo de la herramienta, y convertirlo en el adaptador exige "
            "decidir qué devuelve el dominio en su lugar. Es una decisión de "
            "capas, no un reemplazo de literales."
        ),
    },
    {
        "id": "handler_amplio_en_el_registro_de_la_cli",
        "estado": "saldada",
        "saldada_en": "v40.23",
        "sostenida_por": [
            "tests/test_cli_package.py::test_un_spec_ilegible_no_se_confunde_con_uno_ausente",
            "tests/test_cli_package.py::test_con_el_contrato_ilegible_la_validacion_falla_cerrado",
        ],
        "desde": "v40.9",
        "capa": "5",
        "que": (
            "`cli/registry.py::_load_spec` responde a un `except Exception` con un "
            "vacío indistinguible: un `tool-spec.json` ilegible se presenta como "
            "un catálogo sin entradas (AP-51). Destapado por el mismo ensanche de "
            "alcance de v40.9 y congelado en `blame-baseline.json`. v40.23 "
            "(77981b5) lo cerró con `_leer_spec`, que distingue `ausente`, "
            "`ilegible` y `legible`, y `spec_status` lo expone a `cli doctor`; "
            "el registro siguió diciendo `pendiente` hasta que se midió en v41.3."
        ),
        "por_que_no_ahora": (
            "Distinguir «no hay spec» de «la spec no se pudo leer» cambia lo que "
            "`cli doctor` reporta, y esa salida ya la consumen los repos "
            "consumidores. Se toca con su propio test de contrato."
        ),
    },
    {
        "id": "normas_criticas_sin_detector",
        "estado": "saldada",
        "saldada_en": "v41.4",
        "sostenida_por": [
            "tests/test_ap08_version_pinned.py::test_ap08_vigencia_nombra_la_nota_anclada_a_una_version_que_ya_paso",
            "tests/test_ap08_version_pinned.py::test_ap08_un_universo_vacio_se_publica_y_no_sale_verde_en_silencio",
            "tests/test_ap08_version_pinned.py::test_ap08_vault_write_emite_version_pinned",
            "tests/test_ap08_vigencia.py::test_ap08_vigencia_nombra_la_nota_que_no_acompano_al_cambio",
            "tests/test_ap01_prosa.py::test_ap01_la_ruta_citada_en_prosa_que_no_existe_se_nombra",
            "tests/test_ap01_prosa.py::test_ap01_la_cobertura_parcial_declara_la_prosa_medida",
            "tests/test_ap04_hipotesis.py::test_ap04_no_tiene_detector_y_lo_declara",
        ],
        "desde": "v40.11",
        "capa": "4",
        "que": (
            "Tres normas no las mide nadie y lo declaran por escrito en "
            "`cobertura_descubierta`: AP-01, AP-04 y AP-08. Desde v40.11 eran "
            "cuatro; AP-02, la variante same-folder cuyas hermanas AP-17 y AP-18 "
            "sí pesan en el healthIndex, pasó a `cobertura_parcial` cuando "
            "`vault_audit` empezó a medir la versión que el nombre declara "
            "(`sameFolderVersions`). **El titular de esta entrada era AP-05, la única "
            "`critical` descubierta, y salió en v40.15**: `vault_fuente_unica` "
            "(puerta 16) mide el mismo dato **tipado** —IP, URL, puerto, semver— "
            "con valores distintos en un mismo ámbito. No cerró el problema "
            "general: el catálogo la declara `cobertura_parcial`, porque la "
            "divergencia en prosa, la de valores sin tipo y la del sinónimo "
            "(`ip:` frente a `direccion_ip:`) siguen sin medirlas nadie. La "
            "entrada sigue pendiente por las otras tres, no por AP-05 ni AP-02. "
            "(Avance de v41.3: AP-08 pasó a `cobertura_parcial` con "
            "`vault_drift_detect --mode vigencia`, y AP-01 también, en el mismo "
            "modo: un `files:` que no está en el disco del repo sale en "
            "`codigo_inexistente`. Medido contra la copia de /ans: con la base "
            "buena, 0 AP-01 y 7 AP-08; con `--path` en la raíz, las 7 salían "
            "AP-01, y por eso la respuesta lleva una `pista` cuando no resuelve "
            "ninguno. Queda AP-04 entera, y de AP-01 y AP-08 la parte escrita "
            "en prosa.) (Avance de v41.3, 2026-10-09: AP-01 mide la ruta de "
            "código citada entre backticks, en `prosa_inexistente`. Regla 7 "
            "con la tool, sobre una copia de /ans y su repo en solo lectura "
            "(hash igual antes y después): en las notas del proyecto que "
            "afirman —ni `registro` ni `indice`, ni doc del estándar—, 14 notas "
            "citan una ruta ausente sin otro sitio con el mismo nombre. Las "
            "copias de los otros consumidores no traen historia de git y el "
            "modo vigencia responde `GIT_UNAVAILABLE`, así que no hay cifra "
            "suya; la muestra de /ans contrastada con el original dio "
            "código archivado o renombrado —`core/toon.py` vive en `_archive/` "
            "de /ans— junto a rutas de otro repo indistinguibles, así que "
            "informa sin entrar en `action_required`. Lo que el nombre sí "
            "encuentra en otro sitio —289 en /ans— se cuenta como base ambigua.)"
        ),
        "por_que_no_ahora": (
            "AP-05 tuvo su tanda en v40.15, y lo que la desbloqueó no fue "
            "resolver el problema abierto: fue dejar de plantearlo entero. Un "
            "valor **tipado** no se reconoce por parecido, se compara por "
            "igualdad, y su identidad no se adivina —está escrita al lado, como "
            "clave de un `clave: valor`—. Eso quita la semántica de en medio y "
            "deja una parte decidible, que es la que se mide; el resto se "
            "declara en vez de darse por cubierto. Las tres que quedan siguen "
            "sin una reformulación equivalente, y ninguna es `critical`. "
            "(En v41.3 AP-08 y AP-01 la encontraron en `files:`, que la nota "
            "declara. AP-04 no: su señal decidible es la misma que la de AP-01 "
            "y el discriminador —la intención— no está en ningún campo; el "
            "motivo queda en su `cobertura_descubierta`. El 2026-10-09 se midió "
            "la última hipótesis, la historia del `status` en git, y dio señal "
            "nula en /ans; la cifra vive en esa misma `cobertura_descubierta`. "
            "La parte en prosa de AP-08 tampoco: el `version_pinned:` que la "
            "haría decidible no lo declara ninguna nota de las copias medidas, "
            "y el motivo queda en su `cobertura_parcial`.) Saldada, 2026-10-09, "
            "cerrando lo decidible y declarando el resto, como decidió el "
            "usuario: `version_pinned` entra en el contrato v41 (opcional, mapa "
            "`paquete: versión`), lo emite `vault_write --version-pinned` y "
            "`vault_drift_detect --mode vigencia` lo cruza con el manifiesto de "
            "la raíz del repo, publicando su universo aunque esté vacío "
            "(AP-60). Regla 7 sobre la copia de /ans y su repo en solo lectura: "
            "0 notas lo declaran, y la respuesta lo dice en vez de salir verde. "
            "Lo que queda sin detector —AP-04 entera, la prosa de AP-01 que no "
            "es una ruta y la versión en prosa de AP-08 sin el campo— exige "
            "interpretar el texto, y cada norma lo declara con su cifra medida "
            "en su `cobertura_*`: ninguna queda en silencio ni es `critical`."
        ),
    },
    {
        "id": "fronteras_de_escritura_por_contexto",
        "estado": "saldada",
        "saldada_en": "v41.3",
        "sostenida_por": [
            "tests/test_arch_escrituras_de_sistema.py::test_un_contexto_que_escribe_la_subruta_de_otro_es_un_cruce",
            "tests/test_arch_escrituras_de_sistema.py::test_la_puerta_frena_un_cruce_nuevo_y_no_los_congelados",
            "tests/test_sistema_un_solo_escritor.py::test_la_subruta_la_escribe_solo_su_dueno",
            "tests/test_arch_escrituras_por_parametro.py::test_el_caso_medido_tool_spec_tiene_dueno_y_escritor_visible",
            "tests/test_arch_escrituras_por_parametro.py::test_la_funcion_importada_se_resuelve_un_nivel",
        ],
        "desde": "v40.9",
        "capa": "3",
        "que": (
            "Ningún guard dice qué contexto puede escribir dónde. `00_System` lo "
            "escriben hoy seis contextos. (Cerrada con la decisión del usuario "
            "del 2026-10-08, «registro de subrutas»: `vault_arch.duenos_de_sistema` "
            "deriva el dueño de cada subruta de los `FICHERO_*` de los "
            "repositorios de dominio, y `SUBRUTAS_DE_SISTEMA_SIN_REPOSITORIO` "
            "declara, con motivo, las seis que ninguno declara. "
            "`escrituras_de_sistema_ajenas` bloquea la puerta ante un cruce "
            "nuevo; los cinco que ya existían quedaron en `system_writes` de "
            "`arch-baseline.json`, que solo encoge. Residuo saldado en v41.3 con "
            "el criterio «dueño = único escritor», decidido el 2026-10-08: el "
            "dueño expone la escritura y el otro contexto delega por un par que "
            "ya estaba en el presupuesto; `.tool-tokens.json` pasó al kernel, "
            "que es quien lo escribe, y Consulta lo reexporta anotado. "
            "`system_writes` quedó vacío con el fichero en pie. Cobertura: no ve rutas que "
            "llegan por parámetro desde otro módulo ni subrutas calculadas, y "
            "falla del lado de no marcar. Caso medido el 2026-10-09: "
            "`vault_manifest --bootstrap` escribe `00_System/tool-spec.json` "
            "con `atomic_write_json(tool_spec_path())`; la ruta sale de "
            "`vault_io`, la subruta colapsa a «la carpeta» y no se reporta. "
            "Ese mismo día `tool-spec.json` recibió dueño declarado en "
            "`SUBRUTAS_DE_SISTEMA_SIN_REPOSITORIO` (meta_toolkit, su único "
            "escritor). Desde v41.3 la guarda la ve: `funciones_de_sistema_del_repo` "
            "indexa las funciones cuyo `return` es ruta literal de `00_System/` "
            "y `escrituras_de_sistema_en` las resuelve un nivel en quien las "
            "importa (`from m import f` o `m.f()`); medido ese día, no "
            "apareció ningún cruce nuevo. Sigue fuera: la ruta que llega por "
            "parámetro a un helper de nombre neutro (uno que se llama como una "
            "escritura sí se ve), la función sin import que la resuelva y la "
            "ruta calculada a más de un nivel. "
            "`tests/test_arch_escrituras_por_parametro.py` fija lo que se ve y "
            "lo que no, para que quien lo amplíe tenga que corregir esta "
            "declaración.)"
        ),
        "por_que_no_ahora": (
            "Exige antes sanear `_LLAMADAS_DE_ESCRITURA` —incluye `replace`, que "
            "captura `str.replace`, y `write_report`, que no escribe— y una decisión "
            "de diseño que nadie ha tomado: de quién es `00_System`. (El "
            "saneado está hecho en v41.3: `vault_arch.llamada_de_escritura` es "
            "la única definición de «escribe» de las dos guardas, `write_report` "
            "salió de la lista y `replace` se decide por la forma —de 640 "
            "llamadas que contaban en `scripts/`, 336 no escribían—. Queda la "
            "decisión de dueño, que es del usuario.)"
        ),
    },
    {
        "id": "recursion_error_en_parsers",
        "estado": "saldada",
        "saldada_en": "v40.23",
        "sostenida_por": [
            "tests/test_excepcion_declarada.py::test_ninguna_tool_cae_con_un_frontmatter_muy_anidado",
        ],
        "desde": "v40.9",
        "capa": "5",
        "que": (
            "`RecursionError` escapa a `except yaml.YAMLError` en 4 parsers: no es "
            "subclase. Reproducido a 400 corchetes anidados. El peor caso es "
            "`vault_foreign_check`, que es la tool de la regla 7. v40.23 "
            "(77981b5) lo cerró con AP-61 y su puerta `vault_excepcion_declarada`, "
            "y el test ejecuta el dato hostil contra los parsers reales, "
            "`vault_foreign_check` incluido."
        ),
        "por_que_no_ahora": (
            "Es un arreglo de robustez con su propia norma candidata; entra en la "
            "tanda donde se unifiquen los parsers, no en una de alcance."
        ),
    },
    {
        "id": "parsers_de_frontmatter_divergentes",
        "estado": "saldada",
        "saldada_en": "v41.3",
        "sostenida_por": [
            "tests/test_frontmatter_lector_unico.py::test_ap57_hoy_nadie_lee_el_frontmatter_a_mano",
            "tests/test_vault_write_slug_canonico.py::test_la_nota_nueva_usa_el_slug_canonico",
            "tests/test_aliases_superseded_sin_uso.py::test_nadie_lee_los_nombres_superseded",
            "tests/test_aliases_superseded_sin_uso.py::test_los_nombres_viejos_siguen_definidos_y_anotados",
        ],
        "desde": "v40.9",
        "capa": "7",
        "que": (
            "8 parsers de frontmatter distintos (esa parte, saldada en v41.3: al "
            "medirla eran once lectores por líneas en diez módulos, y todos "
            "delegan en `vault/kernel/frontmatter_parsing.cargar_bloque_tolerante`; "
            "`vault_criterios.medir_lecturas` hace fallar la puerta AP-57 ante uno "
            "nuevo); `vault_write.slugify` no delega en "
            "`vault_lib` aunque 20 módulos sí (esa parte, saldada en v40.35: delega "
            "en `slugify_strict` y el slug viejo queda solo para encontrar notas "
            "ya escritas); 6 aliases de v40.8 con el nombre viejo "
            "aún en uso (esa parte, saldada en v41.3: el repo lee solo los "
            "nombres canónicos y los viejos siguen definidos con su "
            "`superseded_by:`, sin derogarse); `--agent default=\"claude\"` en 6 tools frente al AP-16 que "
            "`vault_bug_save` exige."
        ),
        "por_que_no_ahora": (
            "Es AP-50 acumulado y se salda unificando, no parcheando: hacerlo a "
            "medias deja nueve parsers en vez de ocho. Quedan los aliases y el "
            "`--agent` por defecto, y lo segundo cambia lo que reciben los "
            "clientes MCP: lo decide el usuario, no esta tanda. (Decidido el "
            "2026-10-08: el default se mantiene. Medido ese día, ya son 13 tools "
            "con `default=\"claude\"`, no 6; cambiarlo alteraría lo que "
            "reciben los clientes MCP que no pasan `--agent`, y `vault_bug_save` "
            "sigue exigiéndolo donde la atribución es parte del defecto. Esa "
            "parte queda decidida. Los aliases se migraron ese mismo día, y con "
            "ello la entrada se salda.)"
        ),
    },
    {
        "id": "catch_vacios_en_el_servidor_mjs",
        "estado": "saldada",
        "saldada_en": "v41.3",
        "sostenida_por": [
            "tests/test_ap51_culpar_al_dato.py::test_ap51_el_detector_js_distingue_silencio_de_motivo",
            "tests/test_ap51_culpar_al_dato.py::test_ap51_la_frontera_js_no_tiene_deuda_y_bloquea_la_puerta",
            "tests/test_mcp_descubrimiento.py::test_un_recuento_parcial_de_notas_se_declara",
            "tests/test_mcp_guard_enlaces.py::test_un_directorio_ilegible_no_se_publica_como_nota_inexistente",
        ],
        "desde": "v40.9",
        "capa": "7",
        "que": (
            "11 `catch (_) {}` en `mcp/nodejs/vault-mcp-server.mjs` (AP-51 en JS). "
            "v41.3 los midió uno a uno: los que convertían un fallo en un vacío "
            "—traza, sello de versión, backup, recuento del registro, mapa de "
            "enlaces— ahora lo exponen; los legítimos —caer a un error declarado, "
            "probar el siguiente candidato— lo dicen con `AP-51:`. "
            "`vault_blame_audit.catch_silenciosos_js` mide la frontera JS sin "
            "baseline, con tolerancia cero."
        ),
        "por_que_no_ahora": (
            "Los tres audits con baseline miden AST de Python. Un detector de "
            "JavaScript es otro proyecto, y fingir que el alcance lo cubre sería el "
            "mismo cero sobre un subconjunto que esta versión vino a cerrar."
        ),
    },
    # ── Los cuatro movimientos que v40.20 declara y no ejecuta ───────────────
    #
    # v40.20 fue el movimiento 1 de una arquitectura de cinco. Los otros cuatro
    # entran aquí con nombre en vez de quedarse en una conversación: una deuda
    # que el plano no publica es una deuda que nadie revisa, y ese es
    # exactamente el mecanismo que AP-59 acaba de medir en la lista del kernel.
    {
        "id": "baselines_sin_objetivo_ni_pendiente",
        "estado": "saldada",
        "saldada_en": "v40.24",
        "sostenida_por": [
            "tests/test_baseline.py::test_un_numero_suelto_no_es_un_objetivo",
            "tests/test_baseline.py::test_la_pendiente_no_esta_escrita_en_ningun_fichero",
        ],
        "desde": "v40.20",
        "capa": "7",
        "que": (
            "Las baselines del repo solo podían **encoger**, y eso es un suelo, "
            "no una trayectoria: nada declaraba a cuánto deberían llegar ni a "
            "qué ritmo. v40.24 lo cierra con el mecanismo, no con una cifra: "
            "`vault_baseline` es el dueño único de la carga, la escritura y la "
            "negativa a crecer, y el contrato de `objetivo` exige tamaño, fecha "
            "límite, cadencia y dueño — un número suelto no valida. La "
            "pendiente se deriva de `git log` cada vez que se genera este "
            "plano y **nunca se escribe** en el fichero, porque escribirla "
            "sería afirmar sobre la historia sin que git la respalde (AP-53). "
            "Las dos columnas nuevas de la tabla de abajo son eso. Con ello "
            "`gancho_sin_presupuesto` deja de ser informativo: los seis "
            "`GANCHOS_DEL_KERNEL` declaran presupuesto en "
            "`vault_arch.PRESUPUESTO_DE_GANCHOS` y el séptimo sin declarar "
            "bloquea la puerta."
        ),
        "por_que_no_ahora": (
            "Cerrada. Lo que queda no es esta deuda sino la siguiente, y va "
            "declarada aparte: el mecanismo existe y la mayoría de las "
            "baselines todavía publican `sin objetivo`."
        ),
    },
    {
        "id": "baselines_sin_objetivo_asignado",
        "estado": "saldada",
        "saldada_en": "v41.3",
        "sostenida_por": [
            "tests/test_baseline.py::test_ninguna_baseline_del_repo_queda_sin_compromiso",
            "tests/test_baseline.py::test_dos_baselines_en_un_fichero_tienen_cada_una_su_objetivo",
            "tests/test_baseline.py::test_una_baseline_que_no_es_deuda_lo_declara_con_motivo",
        ],
        "desde": "v40.24",
        "capa": "7",
        "que": (
            "El campo `objetivo` ya existe y se valida, pero solo "
            "`excepcion-declarada-baseline.json` lo declara — y allí el valor "
            "no es una decisión, es lo que la propia baseline ya decía: nació "
            "vacía y el objetivo es que siga vacía. Las demás publican `— sin "
            "objetivo` en la capa 6, que es el estado honesto y no se confunde "
            "con `cumple`. (Saldada en v41.3, 2026-10-09: el usuario aprobó una "
            "propuesta medida —tamaño actual e historia en git de cada baseline— "
            "y cada una declara tamaño, fecha, cadencia y dueño; la capa 6 los "
            "publica. Para escribirlos hubo que ampliar el contrato: "
            "`objetivos_por_clave` cuando un fichero congela dos baselines, y "
            "`sin_objetivo_porque` para el contrato de campos, que crece por "
            "diseño y se publica como `no_aplica` en vez de con una meta falsa.)"
        ),
        "por_que_no_ahora": (
            "A cuánto debe encoger cada baseline y para cuándo es un "
            "compromiso del dueño del repo, no un dato derivable. Escribir "
            "trece cifras plausibles para que la tabla se vea completa sería "
            "exactamente el AP-47 que el contrato de `objetivo` existe para "
            "impedir, cometido dentro del mecanismo que lo impide."
        ),
    },
    {
        "id": "vault_norms_es_un_modulo_dios",
        "estado": "saldada",
        "saldada_en": "v40.27",
        "sostenida_por": [
            "tests/test_arquitectura.py::test_el_catalogo_de_normas_es_una_hoja_del_nucleo",
        ],
        "desde": "v40.20",
        "capa": "7",
        "que": (
            "`vault_norms` acumula miles de líneas y la mayor parte de los "
            "cruces sin puerto del repo. Las dos cifras iban escritas aquí y "
            "las dos habían envejecido —decía 4.257 líneas cuando ya eran más "
            "de cinco mil, y «9 de los 13 cruces» cuando el reparto había "
            "cambiado—, que es AP-47 cometido dentro del registro que publica "
            "la deuda de AP-47; se miden con `wc -l scripts/vault_norms.py` y "
            "con `off_port_crossings` de `scripts/arch-baseline.json`, y por "
            "eso ya no se copian. No es un problema de clasificación —al "
            "medir para v40.20 se comprobó que su fan-in no es el del "
            "núcleo—: es un módulo que hace de catálogo, de motor y de fachada "
            "a la vez, con las dependencias invertidas. Se parte en `catalog` "
            "/ `engine` / fachada y se invierten esos cruces. v40.26 hizo el "
            "corte y v40.27 lo cobró: partido, `vault_norms_catalog` resultó "
            "tener fan-out cero —la forma de `vault_registry`— y se mudó al "
            "núcleo con `compute_norm_refs`. Veintiuno de sus veinticuatro "
            "importadores solo pedían datos y ahora se los piden al dueño: "
            "**62 → 42 cruces, veinte saldados, cero nuevos**, y quince "
            "ciclos diferidos de AP-58 resueltos de paso, porque `vault_voice` "
            "dejó de importar la fachada. La deuda se cierra midiendo, no "
            "declarándolo: el corte por sí solo no movió una sola cifra."
        ),
        "por_que_no_ahora": (
            "Es la tanda más cara de las cinco y depende de lo que el mapa del "
            "núcleo revele. Partirlo antes de tener el grafo con dueño habría "
            "sido mover código a ciegas."
        ),
    },
    {
        "id": "la_norma_no_es_un_paquete",
        "estado": "saldada",
        "saldada_en": "v41.4",
        "sostenida_por": [
            "tests/test_normas_caras.py::test_todo_paquete_tiene_sus_cinco_caras",
            "tests/test_normas_caras.py::test_las_caras_en_disco_son_las_derivadas",
            "tests/test_normas_caras.py::test_un_sanador_que_no_nombra_la_norma_falla_la_forma",
            "tests/test_normas_caras.py::test_una_cara_editada_a_mano_se_detecta",
            "tests/test_normas_paquete.py::test_la_guarda_ve_la_cara_que_falta",
        ],
        "desde": "v40.20",
        "capa": "7",
        "que": (
            "El ciclo obligatorio del repo —síntoma → norma → guard+audit+heal → "
            "test— vive hoy en cuatro listas sincronizadas a mano: el catálogo, "
            "la tool, la puerta y el fichero de tests. La norma como **paquete** "
            "(`normas/AP-XX/` con `norma.py`, `guard.py`, `heal.py`, `test_*.py` "
            "y `porque.md`) la convierte en una sola cosa con cuatro caras, y el "
            "coste de una norma nueva deja de crecer con la historia del repo."
        ),
        "por_que_no_ahora": (
            "Migra por atrición, no de golpe: 71 normas movidas en una tanda "
            "serían 71 oportunidades de perder un matiz. Empieza por las que se "
            "escriban a partir de ahora.\n\n"
            "(Avance de v41.3, fecha: 2026-10-09.) La infraestructura existe y "
            "tiene piloto: AP-65, la última norma del catálogo, vive en "
            "`normas/AP-65/` con `norma.py`, `porque.md` y su test. "
            "`vault_norms_catalog` la carga en su sitio de siempre —el catálogo "
            "y el registro que reconstruye `vault_norms --rebuild` no cambiaron "
            "ni un byte, salvo la fecha—; `--check-framework` falla si un "
            "paquete pierde una cara, declara otro código, no lo carga el "
            "catálogo o cita en `porque.md` una cara `ruta::símbolo` que no "
            "existe; `normas/` viaja en la wheel y lo comprueba "
            "`clean_install_gate`. Lo que no tiene el piloto, y se declara: "
            "`guard.py` y `heal.py` propios. Su criterio sigue con su dueño en "
            "el kernel y AP-65 no tiene heal, porque nadie puede escribir por "
            "otro a quién afecta una decisión. Queda la migración del resto, "
            "una norma cada vez. (2026-10-09: AP-64, la anterior a la piloto, "
            "vive en `normas/AP-64/`; el catálogo serializado sale idéntico al "
            "de antes de moverla y sus tests de `tests/` siguen donde estaban. "
            "Cuántas van lo publica `vault_norms_catalog.NORMAS_EN_PAQUETE`.) "
            "(2026-10-09, m183–m186: el resto migró por familias —patrones, "
            "protocolos y convenciones en un lote; AP en tres tramos—. "
            "`NORM_CATALOG` ya no escribe ninguna entrada: toda norma la carga "
            "`_desde_paquete`, el catálogo serializado sale idéntico byte a "
            "byte al de antes del primer lote y `--rebuild` no escribe nada. "
            "Las caras de `porque.md` se derivaron al migrar, no se "
            "escribieron, y donde una tool declarada no tiene función que "
            "nombre la norma lo dice en vez de inventarla. Lo que sigue "
            "pendiente es lo que el piloto ya declaraba: `guard.py` y "
            "`heal.py` propios. El criterio de cada norma sigue con su dueño "
            "en `scripts/` o `vault/`, y moverlo a la carpeta sería la "
            "segunda copia que el paquete viene a quitar, así que esta deuda "
            "no se salda solo por haber migrado las entradas.)\n\n"
            "(2026-10-09, m197: saldada.) `guard.py` y `heal.py` existen en "
            "cada paquete y son **derivados**, no escritos: cada "
            "`ruta::símbolo` es una función que nombra la norma en su cuerpo "
            "dentro de una tool que el catálogo declara, así que apuntan al "
            "dueño sin copiar su criterio. Las tools que reparan salen de un "
            "registro nuevo con dueño, `vault_norms_catalog.SANADORES`, que es "
            "por tool y no por norma; `tools_healing(code)` se deriva de él. "
            "Una norma sin sanador lleva `HEAL = None` con su `MOTIVO`, y un "
            "par del registro sin función que lo nombre falla la puerta "
            "(AP-55). `--check-framework` falla si una cara falta o no es la "
            "que sale de derivarla, y la wheel las lleva."
        ),
    },
    {
        "id": "el_vault_no_tiene_kernel_declarado",
        "estado": "saldada",
        "saldada_en": "v41.4",
        "sostenida_por": [
            "tests/test_sanacion_orden_por_nucleo.py::test_la_fase_8_repara_primero_las_notas_del_nucleo",
            "tests/test_sanacion_orden_por_nucleo.py::test_sin_nucleo_el_orden_es_por_enlaces_rotos_y_lo_dice",
            "tests/test_sanacion_orden_por_nucleo.py::test_el_plan_sigue_siendo_de_solo_lectura",
        ],
        "desde": "v40.20",
        "capa": "7",
        "que": (
            "`vault_kernel` traza el núcleo **del repo**. El mismo concepto "
            "aplicado a las notas —qué subconjunto de un vault es su núcleo— "
            "daría prioridad a `vault_context_pack` cuando el paquete no cabe, "
            "orden a la sanación y pesos a `vault_audit`."
        ),
        "por_que_no_ahora": (
            "Declarado sin fecha por decisión de alcance. El núcleo de un vault "
            "no se deriva del grafo de imports sino del de enlaces, y esa medida "
            "hay que contrastarla contra un vault ajeno antes de creérsela "
            "(regla 7). (Avance de v41.3, 2026-10-09: la medida existe y es "
            "informativa. `vault_audit._nucleo_del_vault` cuenta el fan-in de "
            "cada nota desde notas de contenido distintas, resuelto como "
            "Obsidian —nombre, `aliases:`, sufijo de carpeta, nunca `title:`—, "
            "y corta con el mismo escalón que `vault_kernel`, que pasa a "
            "`vault/kernel/escalon.py` para tener un solo dueño; sale en "
            "`vaultCore` sin fila en `PENALIZACIONES`. Regla 7 sobre copias "
            "nuevas, hash de los originales intacto: /ans, 527 notas, umbral "
            "29 (ratio 1.933), una nota núcleo, `01_Projects/ans/overview.md`; "
            "/vcloud, 106 notas, umbral 26 (ratio 1.444), una nota núcleo, "
            "`09_Infrastructure/network-topology.md`. Sigue pendiente lo que la "
            "medida habilita y no hace todavía: la prioridad en "
            "`vault_context_pack`, el orden de la sanación y cualquier peso. "
            "Medida y descartada, 2026-10-09: la prioridad en el paquete —las "
            "candidatas del núcleo entran primero cuando la ventana no cabe, "
            "sin traer ninguna que la consulta no recuperó— se implementó y se "
            "midió con recall título → paquete sobre copias nuevas, y **baja** "
            "el recall: /vcloud a 500 tokens de 1.0 a 0.76; /ans a 800 de 0.96 "
            "a 0.92 y a 500 de 0.84 a 0.80; la nota buscada en primera "
            "posición cae en los dos (vcloud de 1.0 a 0.76–0.80, ans de 0.84 a "
            "0.72). La causa es la del corte: el núcleo es una nota-hub que el "
            "grafo trae como candidata a casi toda consulta, y adelantarla "
            "desplaza a la que la consulta buscaba. Revertida, como pedía el "
            "criterio fijado antes de medir. Lo que queda habilitado es "
            "orden de sanación o peso, y ninguno se mide todavía. Saldada, "
            "2026-10-09, con las tres salidas decididas: la prioridad en el "
            "paquete, descartada por medida (arriba); el peso en el "
            "`healthIndex`, descartado por el usuario; y el orden de la "
            "sanación, hecho: la fase 8 de `vault_sanacion` publica `order` "
            "—las notas de `vaultCore` con enlaces rotos primero, luego por "
            "fan-in y por enlaces rotos— y `order_criterion`, sin escribir "
            "nada ni decidir qué enlace es nota ausente. Regla 7 sobre las "
            "mismas copias, hash intacto antes y después: en /ans (18 notas "
            "con rotos) y /vcloud (6) la única nota núcleo no tiene enlaces "
            "rotos, así que allí el orden coincide hoy con el recuento; el "
            "criterio existe y se declara, no cambia nada en esos dos vaults.)"
        ),
    },
    {
        "id": "puente_scripts_impl_sin_contrato",
        "estado": "pendiente",
        "desde": "v40.34",
        "capa": "3",
        "que": (
            "`_impl/` no es una copia de `scripts/`: es el destino del "
            "package-dir que mapea `scripts/` → `vault_toolkit/_impl/`. "
            "ADR-0002 formaliza el puente: fachada de re-export + package-dir. "
            "La deuda es transitoria: desaparece cuando `scripts/` migre a "
            "`vault/<contexto>/` y el puente ya no sea necesario. (Avance de "
            "v41.3, 2026-10-09: la cifra ya no se escribe a mano. "
            "`vault_arch.modulos_sin_hogar` cuenta los módulos de `scripts/` "
            "que no importan nada de `vault/<su contexto>/`, la capa 3 la "
            "publica derivada y la baseline `bridge_modules` de "
            "`arch-baseline.json` la congela: solo encoge, y un módulo nuevo "
            "sin hogar bloquea `vault_arch --check`. Primera migración, para "
            "probar que el puente aguanta: `vault_subproceso`, hoja del kernel, "
            "vive en `vault/kernel/subproceso.py` y `scripts/` conserva el "
            "nombre como fachada; la wheel limpia lo importa desde `_impl`. "
            "Segunda, el mismo 2026-10-09: `vault_ledger`, el contador "
            "thread-local de AP-37, vive en `vault/kernel/ledger.py` y la "
            "fachada reexporta el mismo `threading.local`, también sus nombres "
            "privados, porque `vault_io` los reexporta a su vez. Medida "
            "corregida el mismo día: la cifra contaba también los módulos que "
            "la wheel no lleva —`empaquetado/fuera-de-la-wheel.json`, la "
            "gobernanza del estándar—, que no cruzan el puente porque no "
            "viajan; excluidos, la baseline perdió 22 entradas sin ganar "
            "ninguna. Lote A, 2026-10-09: cuatro hojas sin `__file__` ni "
            "lectores del fuente por ruta —`vault_audit_catalog`, "
            "`vault_fundamentals_catalog` y `vault_mermaid_reglas` al kernel, "
            "`vault_security_rules` a gobernanza—, ya como alias en "
            "`sys.modules` y no como fachada que reexporta, para que un "
            "monkeypatch sobre el nombre viejo lo vea el dueño; wheel limpia "
            "y `run_product_gates` en verde. Quedan fuera del lote, con "
            "motivo: `vault_norms_catalog` y `vault_entorno` (otros módulos y "
            "tests leen su fuente por ruta), `vault_grafo_import` (usa "
            "`__file__`), `vault_secret_scan` (lo leen por ruta tres tests y "
            "`vault_standard_upgrade`) y `vault_version` (lo lee `cli/`). "
            "Lote B, 2026-10-09: `vault_secret_scan` a gobernanza. Lo que lo "
            "frenaba no eran los lectores —`vault_standard_upgrade` solo lo "
            "nombra en una cadena— sino que es CLI: un alias en `sys.modules` "
            "no ejecuta el `__main__` del dueño, así que el alias de una tool "
            "con CLI lo delega con `runpy`. Los guards que leen el fuente de "
            "una tool siguen el alias hasta el dueño por un solo sitio, "
            "`vault_grafo_import.fuente_de`. `vault_version` sigue fuera: "
            "`cli/` ejecuta su fichero con `spec_from_file_location` para no "
            "tocar `sys.path`, y un alias no tiene `CURRENT_VERSION`. "
            "Lote C, 2026-10-09: `vault_entorno` al kernel —el motivo que lo "
            "dejó fuera del lote A no se sostuvo al medirlo: el `.mjs` y "
            "`env-table.json` lo nombran en prosa y la tabla se deriva por "
            "import—. Lo que queda son cadenas: `vault/` solo importa de "
            "`scripts/` por `vault/kernel/adaptadores.py`, así que un módulo "
            "con dependencias en `scripts/` no migra como alias sin reescribir "
            "sus imports; las raíces que las bloquean son `vault_norms_catalog` "
            "(`__file__` para `normas/` y tests que leen su fuente: punto de "
            "la deuda #10), `vault_version` y `vault_grafo_import`. "
            "Lote D, 2026-10-10: `vault_link_safety` a grafo, "
            "`vault_escaneo_grafo` al kernel, `vault_firma_sitio` a "
            "meta_toolkit y `vault_index` a índices. La frase anterior sobre "
            "cadenas era más estricta que la regla medida: `vault_arch` solo "
            "marca un cruce cuando un módulo de `vault/<ctx>/` importa uno de "
            "**otro contexto que no es el kernel**, así que una hoja cuyas "
            "dependencias en `scripts/` son del kernel o de su contexto migra "
            "sin puerto; los cruces no se movieron. Lo destapó la guarda de "
            "puertos, que leía el fichero del alias y dio por roto "
            "`resolver_wikilink`: ahora sigue el alias con `fuente_de`, como "
            "un import.)\n\n"
            "(Lote E, 2026-10-10: ocho tools con CLI migran —append, list, "
            "log_error, merge, project_status y runbook_log a autoría, section "
            "a índices como `registro_de_secciones` y env_matrix a grafo—; el "
            "alias corre su `main` con `runpy`. Los tests de AP-46 y del barrido "
            "de secciones leían la ruta del alias y ahora siguen al dueño, y las "
            "caras de CN-02 citan `vault/indices/registro_de_secciones.py`.)\n\n"
            "(Lote F, 2026-10-10: seis migran —history_compact y arquitectura_en "
            "a ciclo de vida, graph_fix a grafo, supersede, frontmatter_completar "
            "y frontmatter_heal a autoría—, y las caras de las catorce normas que "
            "los citaban apuntan al dueño. `vault_subgraph` se quedó en "
            "`scripts/`: su cruce hacia `vault/grafo` está en la baseline con la "
            "clave del nombre de `scripts/`, y moverlo lo re-clavaba como cruce "
            "nuevo. Es la misma traba que la de las cinco firmas de las "
            "baselines de AP-51 y AP-57: la clave tiene que seguir al alias. "
            "Desde que la sigue —`vault_arch.alias_de_dueno`—, `vault_subgraph` "
            "migra a `vault/consulta/subgraph.py` con su cruce intacto.)\n\n"
            "(Lote H, 2026-10-10: los cinco con sitios en baselines —errors_trace "
            "al kernel, fix_brackets a autoría, graph_inspect a grafo, sanacion a "
            "ciclo de vida y spec_generate_catalog a meta_toolkit— migran sin "
            "re-clavar nada: blame y criterios ya indexaban por el alias, y "
            "`cruces_fuera_de_puerto` pasó a hacerlo al destapar que medía los "
            "dueños por `ruta.stem` (m245). Las caras de AP-22 y AP-24 citan "
            "`vault/autoria/fix_brackets.py`.)\n\n"
            "(Lote G, 2026-10-10: mcp, spec_catalog_check y test_runner a "
            "meta_toolkit, fuente_unica a gobernanza y token_counter a consulta. "
            "Sus `SCRIPTS_DIR` y baselines se derivaban de `__file__`; ahora salen "
            "de `vault_grafo_import.DIRECTORIO`, que es `scripts/` en el checkout y "
            "`_impl/` en la wheel. Antes, m248 hizo que los tests de propiedad "
            "leyeran al dueño con `codigo_de`. Las caras de AP-05 citan "
            "`vault/gobernanza/fuente_unica.py`. Quedan las nueve raíces del kernel.)\n\n"
            "(Lote D, raíces del kernel, 2026-10-10: version, vocabulario y "
            "contrato_nota a `vault/kernel/`. `cli/__init__.py` lee la versión del "
            "dueño en el kernel —la CLI no viaja en la wheel—, el README de "
            "`schemas/` cita `vault/kernel/contrato_nota.py` y la cara de AP-64 "
            "también. Antes, m251 hizo que `vault_grafo_import.grafo()` midiera al "
            "dueño y no al alias: con las aristas del alias el escalón de AP-59 "
            "bajaba y `vault_errors` cruzaba un umbral que con las reales no cruza.)"
        ),
        "por_que_no_ahora": (
            "Transitorio hasta migrar scripts → vault/<contexto>, ADR-0002. "
            "La fachada y el package-dir existen; la deuda es de diseño, no de implementacion."
        ),
    },
    # Las cuatro siguientes salieron en la ronda de v41.2 (regla 7 sobre copias
    # de /ans y /vcloud, y revisión de normas). Hasta aquí vivían solo en el
    # informe de la ronda: deuda escrita fuera del registro, que el plano no
    # publica y ninguna puerta mira.
    {
        "id": "cn01_cn04_solo_se_miden_al_escribir",
        "estado": "saldada",
        "saldada_en": "v41.3",
        "sostenida_por": [
            "tests/test_cn01_cn04_audit_informativo.py::test_cn01_cn04_se_publican_sin_peso",
            "tests/test_cn01_cn04_audit_informativo.py::test_cn01_cn04_no_mueven_la_salud",
            "tests/test_cn04_escritores_con_titulo.py::test_la_nota_que_crea_el_escritor_abre_con_h1",
        ],
        "desde": "v41.1",
        "capa": "7",
        "que": (
            "CN-01 (nombre kebab-case) y CN-04 (la nota abre con su título como "
            "H1) tienen enforcement `guard` y se cumplen solo en el write path: "
            "`vault_write`, `vault_knowledge_save` y `vault_ai_decision`. Una "
            "nota escrita por otro camino —un vault preexistente, una edición a "
            "mano— no la mide nadie después. El docstring de `vault_write.slugify` lo "
            "dice de CN-01: «ninguna otra tool audita después los nombres ya "
            "escritos». El único `\"norm\": \"CN-01\"` de `vault_audit` es "
            "sobre el scaffold, no sobre los nombres de las notas. (La medida, "
            "hecha en v41.3: `vault_audit._detect_convenciones_cn01_cn04` las "
            "publica en `issues.cn01NotKebab`/`cn04NoTitle`, sin peso, con el "
            "criterio de `slugify_strict` y `abre_con_h1`. Regla 7, 2026-10-08, "
            "sobre copias, repetida igual sobre copias nuevas el 2026-10-08: /ans 94 "
            "y 253 de 527 notas, /vcloud 1 y 0 de 108. De "
            "las 253 de /ans, 137 son de `11_Code`: `vault_code_module` y otros "
            "escritores del estándar no pasan por `con_titulo`.)"
        ),
        "por_que_no_ahora": (
            "Medirlas en notas existentes cambia el enforcement a `guard+audit` "
            "y, si penalizan, el healthIndex de todo vault consumidor. Es una "
            "decisión de norma, con su tabla de penalizaciones y su contraste "
            "contra un vault ajeno antes de fijar el peso (regla 7), no un "
            "arreglo de la tanda. Queda: decidir el peso —lo decide el "
            "usuario— y que los escritores que no aplican `con_titulo` lo "
            "hagan, que cambia su salida. (Decidido el 2026-10-08: sin peso; "
            "la medida sigue informativa. Y los diez escritores que creaban la "
            "nota sin H1 —bug, code_module, diagram, flow, test, requirement, "
            "infra_save, infra_map, pattern y runbook— pasan por `con_titulo`; "
            "sus dorados cambian solo en esa línea. `vault_onboard` ya escribía "
            "el H1 en sus plantillas y `vault_undo` restaura el contenido tal "
            "cual, que es lo que debe hacer.)"
        ),
    },
    {
        "id": "ap17_compara_solo_la_forma_del_titulo",
        "estado": "saldada",
        "saldada_en": "v41.3",
        "sostenida_por": [
            "tests/test_ap17_identidad_declarada.py::test_un_alias_que_es_el_nombre_de_otra_nota_es_sombra",
            "tests/test_ap17_identidad_declarada.py::test_el_mismo_conjunto_de_files_es_sombra_y_uno_distinto_no",
            "tests/test_ap17_identidad_declarada.py::test_el_title_no_es_identidad",
            "tests/test_ap17_identidad_declarada.py::test_la_identidad_se_publica_sin_peso_y_el_titulo_sigue_pesando",
        ],
        "desde": "v41.1",
        "capa": "4",
        "que": (
            "AP-17 (sombra canónica) se detecta con `SequenceMatcher` ≥ 0.85 "
            "sobre el texto del título (`vault_audit._detect_canonical_shadow`). "
            "Dos notas sobre lo mismo con títulos distintos no salen, y dos "
            "títulos parecidos de cosas distintas solo se separan si "
            "`_distintos_por_convencion` reconoce la convención. La atribución "
            "que esta entrada también reclamaba ya estaba bien y se corrigió "
            "aquí en v41.3: el catálogo declara `tools_detecting: "
            "['vault_audit']`, quien mide, y `tools_enforcing: "
            "['vault_supersede']`, quien sana. Lo pendiente es solo la medida. "
            "(Saldada en v41.3 con la reformulación decidible: se compara la "
            "identidad que la nota **declara** —un `aliases:` que es el nombre "
            "de fichero o el alias de otra, o el mismo conjunto de `files:`—, "
            "con el criterio de resolución de Obsidian. Cada par publica su "
            "`motivo`. Regla 7, 2026-10-09, solo lectura y hash intacto: "
            "contra las copias de /ans, /vcloud, builderx, electron, synesis, "
            "smart-pos-cr, ecommerce y grooming-scheduler, 0 pares por `alias` "
            "o `files` y los de `titulo` sin cambio (112, 1, 0, 1, 0, 2, 9, "
            "13). Sin un solo acierto no hay dato con el que fijar un peso, así "
            "que `canonicalShadowIdentity` se informa sin pesar, como AP-02. "
            "Lo que sigue sin medir —el mismo tema con identidad distinta— lo "
            "declara la `cobertura_parcial` de AP-17.)"
        ),
        "por_que_no_ahora": (
            "Ir más allá de la forma pide comparar contenido o identidad "
            "declarada, que es justo lo que el servicio descarta sin embeddings. "
            "Hace falta una reformulación decidible, como la que desbloqueó "
            "AP-05 en v40.15, antes de tocar el detector."
        ),
    },
    {
        "id": "churn_del_kernel_no_ve_el_commit_en_curso",
        "estado": "saldada",
        "saldada_en": "v41.3",
        "sostenida_por": [
            "tests/test_kernel_aviso_del_indice.py::test_el_commit_que_cruza_el_umbral_se_avisa_antes_de_hacerse",
            "tests/test_kernel_aviso_del_indice.py::test_la_cifra_canonica_no_cuenta_el_indice",
            "tests/test_kernel_aviso_del_indice.py::test_el_pre_commit_pide_el_aviso_y_no_bloquea",
        ],
        "desde": "v41.1",
        "capa": "7",
        "que": (
            "K3 de `vault_kernel` (AP-59) cuenta el churn con `git log`, así que "
            "la puerta que corre antes de commitear no ve el commit que se está "
            "haciendo. El que cruza el umbral pasa en verde y el siguiente, "
            "aunque no toque el módulo, hereda el rojo. Pasó en esta ronda: "
            "`vault_registry` llegó a churn 23 con umbral 22.85 (mediana 13 × "
            "1.758) y hubo que admitirlo en `kernel-baseline.json` con "
            "autorización expresa."
        ),
        "por_que_no_ahora": (
            "Contar el índice (`git diff --cached --name-only`) arregla el "
            "pre-commit pero hace que la misma medida dé cifras distintas según "
            "se ejecute antes o después de commitear, y la CI mide después. "
            "Hay que decidir cuál es la medida canónica antes de cambiar el "
            "contador. (Decidido el 2026-10-08: la canónica es la de `git "
            "log`, la que mide la CI. `vault_kernel --aviso-indice` lee el "
            "índice con el mismo criterio de comportamiento y el pre-commit "
            "avisa del cruce sin bloquear ni cambiar la cifra publicada.)"
        ),
    },
    {
        "id": "meta_decide_el_orden_del_frontmatter",
        "estado": "saldada",
        "saldada_en": "v41.3",
        "sostenida_por": [
            "tests/test_orden_frontmatter_contrato.py::test_type_por_meta_sale_donde_el_type_deducido",
            "tests/test_orden_frontmatter_contrato.py::test_los_campos_del_contrato_siguen_a_campos_y_los_ajenos_van_al_final",
            "tests/test_orden_frontmatter_contrato.py::test_sin_campos_del_contrato_en_meta_la_salida_no_cambia",
        ],
        "desde": "v41.1",
        "capa": "5",
        "que": (
            "En `vault_write`, los campos que llegan por `--meta` se añaden al "
            "final del frontmatter. Medido el 2026-10-07: con "
            "`--meta '{\"agent\":\"claude\",\"type\":\"concept\"}'`, `type` sale "
            "detrás de `agent` y de los tres `cia_*`, y su posición depende de por "
            "dónde llegó y no de qué campo es."
        ),
        "por_que_no_ahora": (
            "Ningún consumidor que lea con `yaml.safe_load` depende del orden, "
            "así que no rompe nada. Fijar un orden canónico cambia byte a byte "
            "la salida de toda nota nueva, y ese orden tiene que salir del "
            "contrato de nota (`vault_contrato_nota`), no de una lista nueva. "
            "Saldada en v41.3 con el orden mínimo que eligió el usuario: el "
            "`type` de `meta` ocupa el hueco del deducido, el resto de campos de "
            "`CAMPOS` sale tras `agent` en su orden y lo ajeno al contrato al "
            "final; una nota sin esos campos en `meta` no cambia un byte."
        ),
    },
    {
        "id": "backlinks_del_audit_indexados_por_nombre",
        "estado": "saldada",
        "saldada_en": "v41.3",
        "sostenida_por": [
            "tests/test_audit_backlinks_como_obsidian.py::test_los_homonimos_no_comparten_entrantes",
            "tests/test_audit_backlinks_como_obsidian.py::test_un_enlace_ambiguo_cuenta_para_todas_las_homonimas",
            "tests/test_audit_backlinks_como_obsidian.py::test_una_nota_unica_conserva_su_clave_por_nombre",
        ],
        "desde": "v41.3",
        "capa": "5",
        "que": (
            "`vault_audit._build_indexes` indexa los backlinks por **nombre de "
            "fichero**, no por ruta: dos notas homónimas en carpetas distintas "
            "comparten entrantes, y un enlace que fija una de ellas con su "
            "carpeta deja a la otra «enlazada» también. Es un falso verde en "
            "`orphans` y en `notIntegrated`. Medido el 2026-10-09 en una copia "
            "de /ans: `[[code/playbook-versioning]]` resuelve a "
            "`05_Patterns/code/playbook-versioning.md` y saca de huérfanas a "
            "`11_Code/ans/playbook-versioning.md`, que no enlaza nadie."
        ),
        "por_que_no_ahora": (
            "Pasar la clave a ruta cambia la forma del índice que leen "
            "`_detect_orphans`, `_detect_no_integradas` y cinco ficheros de "
            "tests, y es un arreglo distinto del que la destapó: m155 hizo que "
            "los backlinks resolvieran alias, carpeta y ancla como Obsidian "
            "(AP-44), y con eso el caso homónimo se hizo visible. El test "
            "`tests/test_audit_backlinks_como_obsidian.py::"
            "test_limite_declarado_los_homonimos_comparten_entrantes` fija el "
            "límite y falla el día que se salde. (Saldada en v41.3, "
            "2026-10-09, sin cambiar la forma del índice para nadie más: "
            "`vault_audit._claves_de_nota` indexa por nombre a la nota única y "
            "por ruta a cada homónima, también como origen, y los detectores "
            "leen con `_clave_de`. Un enlace ambiguo sigue contando para todas "
            "las candidatas. Regla 7 sobre copias nuevas, hash de los "
            "originales intacto: /ans, huérfanas 2 → 2 y no integradas "
            "271 → 274 —`10_Migrated/direct/claude-code-setup.md`, "
            "`10_Migrated/excluded/codex-guide.md` y "
            "`11_Code/ans/playbook-versioning.md`, sin ningún wikilink "
            "saliente y citadas solo por su `index.md`: se integraban con los "
            "salientes de su gemela—; /vcloud, sin cambios (12 y 2); "
            "healthIndex igual en los dos. La medida de arriba erraba en un "
            "punto: a `playbook-versioning` sí la cita un índice, así que el "
            "falso verde era de `notIntegrated`, no de `orphans`.)"
        ),
    },
    {
        "id": "f8_criterio_sin_decidir",
        "estado": "saldada",
        "saldada_en": "v41.6 (2026-10-15)",
        "sostenida_por": [
            "tests/test_f8_vault_write_anota.py::test_vault_write_anota_la_creacion_y_la_actualizacion",
            "tests/test_f8_vault_write_anota.py::test_f8_registro_matriz_y_manifiesto_dicen_lo_mismo",
        ],
        "desde": "v41.3",
        "capa": "5",
        "que": (
            "F8 (no repudio) se mide con un criterio que el manifiesto no "
            "publica. El registro (`vault_fundamentals_catalog`, F8) verifica "
            "que «al menos una entrada en .change-log.json referencia la ruta "
            "de la nota» y `vault_quality_check._score_non_repudiation` lo "
            "aplica a toda nota viva; la tabla de dimensiones del manifiesto "
            "pide «1 por borrado». Como `vault_write` no anota creaciones en el "
            "change-log, un vault recién poblado puntúa 0 en `non_repudiation` "
            "en todas sus notas: 26 de 26, medido el 2026-10-14 con la wheel "
            "instalada en un consumidor limpio."
        ),
        "por_que_no_ahora": (
            "Cuál de los dos criterios manda es una decisión de producto: "
            "(a) `vault_write` anota creaciones y actualizaciones, lo que es un "
            "campo nuevo en su contrato, o (b) el registro se ciñe a borrados y "
            "movimientos, como dice el manifiesto. El usuario la dejó declarada "
            "el 2026-10-14. `tests/test_f8_criterio_sin_decidir.py::"
            "test_limite_declarado_f8_registro_y_manifiesto_divergen` fija la "
            "divergencia y falla el día que los dos digan lo mismo. (Saldada "
            "el 2026-10-15: el usuario eligió (a). `vault_write` anota cada "
            "alta y cada cambio en `.change-log.json` y lo publica en el campo "
            "nuevo `change_log` de su envelope —`change_log_error` si la "
            "bitácora falla, sin tumbar la escritura—; la matriz y el "
            "manifiesto pasan a «1 por nota», que es lo que el registro ya "
            "medía, y `vault_write` entra en las tools de F8. El criterio no "
            "se rebajó: una nota viva sin entrada sigue puntuando 0.)"
        ),
    },
    {
        "id": "sanadores_sin_lote",
        "estado": "pendiente",
        "desde": "v41.4",
        "capa": "5",
        "que": (
            "AP-47: `vault_io.escrituras_en_lote()` regenera sección, búsqueda "
            "y grafo una vez por lote en vez de una vez por nota. Lo abren "
            "`vault_frontmatter_completar` (2990 s → 32 s) y la ruta "
            "clasificada de `vault_graph_fix` (107 s → 15 s), y desde el "
            "2026-10-16 `vault_fix_brackets` (58,8 s → 11,5 s sobre 50 notas "
            "sembradas en una copia de /ans: sin lote moría por TOOL_TIMEOUT) "
            "y `vault_frontmatter_heal` (59,6 s → 11,9 s sobre 45 notas con el "
            "frontmatter sembrado en una copia de /ans; 13,8 s → 4,6 s en /vcloud) "
            "y `vault_project --heal` (29,6 s → 9,5 s en /ans; 16,0 s → 5,1 s "
            "en /vcloud) y `vault_graph_fix.apply_fix`: en una copia de /ans, "
            "sin lote, escribir una nota regeneraba el `index.md` de su sección "
            "y los dos índices que venían en el mismo informe salían como "
            "STALE_REPORT —10 de 12 aplicados, rc 1—; con lote, 12 de 12. "
            "`vault_supersede` no lo abre porque escribe una nota por llamada "
            "y no tiene nada que aplazar (medido en "
            "`test_vault_supersede_escribe_una_nota_por_llamada`). "
            "No lo abre `vault_norms_engine`. "
            "Medido el 2026-10-14 sobre 35f5bad."
        ),
        "por_que_no_ahora": (
            "Cada sanador que entra en el lote exige comparar el árbol de dos "
            "copias de un vault ajeno —con lote y sin él— y no solo el "
            "contador, como se hizo con los dos primeros; ninguno de los "
            "restantes ha dado un TOOL_TIMEOUT medido. "
            "`tests/test_sanadores_sin_lote.py::"
            "test_limite_declarado_sanadores_sin_lote` fija la lista y falla "
            "en cuanto encoge o crece. El árbol se compara sembrando el defecto "
            "en hasta 3 notas por carpeta de una copia de /ans y de /vcloud "
            "—el defecto real está en una nota o en ninguna, y así el lote no "
            "se ejercita— y quitando marcas de tiempo y orden de listas JSON "
            "antes de comparar."
        ),
    },
    {
        "id": "spec_validate_returns_ciego",
        "estado": "saldada",
        "saldada_en": "tras v41.7 (2026-10-16, superseded_by vault_smoke)",
        "sostenida_por": [
            "tests/test_ci_sin_enmascarar.py::test_returns_match_queda_superseded_por_el_smoke",
            "tests/test_ci_sin_enmascarar.py::test_spec_validate_no_da_por_ausente_lo_que_no_vive_en_scripts",
            "tests/test_ci_sin_enmascarar.py::test_spec_validate_es_paso_duro_de_la_ci",
        ],
        "desde": "v41.6",
        "capa": "5",
        "que": (
            "AP-44: `vault_spec_validate` comprueba `declared_returns` de "
            "`tool-spec.json` contra las claves escritas como literal en un "
            "`return {...}` (o en el dict asignado a la variable que se "
            "devuelve). No ve `r['clave'] = …`, `r.update(...)` ni las claves "
            "que pone un ayudante común —el indicador de trabajo de AP-37, el "
            "envelope de `emit_error`—, así que da drift a 90 de 145 tools y "
            "8 «missing» que son tools del servidor JS. La CI lo ejecutaba con "
            "`|| echo \"not yet implemented\"`. Medido el 2026-10-15 sobre "
            "72bee01."
        ),
        "por_que_no_ahora": (
            "Ampliar el AST a asignaciones por subíndice y `update` se midió: "
            "baja de 98 a 95 sin pasar, porque el grueso lo ponen ayudantes de otro "
            "módulo. Medirlo con el criterio del consumidor exige ejecutar "
            "cada tool y leer su envelope, que es lo que ya hace `vault_smoke` "
            "por otra vía; decidir si este detector se reescribe o se anota "
            "`superseded_by` es una decisión de producto. Mientras, la CI lo "
            "corre con `continue-on-error` y el nombre del paso cita esta "
            "deuda. `tests/test_ci_sin_enmascarar.py::"
            "test_limite_declarado_spec_validate_returns_ciego` fija el punto "
            "ciego y falla el día que el detector lo vea. "
            "Saldada el 2026-10-16 por decisión del usuario: `returns_match` "
            "queda superseded_by `vault_smoke.contract_gap`, que contrasta el "
            "envelope emitido, y sigue detrás de `--returns-estatico` "
            "(no-derogación). Sin él, lo que quedaba eran 8 «missing» que no "
            "viven en `scripts/` por diseño —5 archivadas, 2 JS nativas y "
            "`vault_gobernanza`, que es `execution_module`— y un drift real "
            "(`vault_qa_save` publicaba `--qa_type`, saldado en d6adcdd). La "
            "tool pasa en verde y la CI la corre como paso duro."
        ),
    },
    {
        "id": "ap37_mide_lo_declarado",
        "estado": "pendiente",
        "desde": "tras v41.6",
        "capa": "4",
        "que": (
            "AP-44 sobre AP-37: `vault_noop_audit` comprueba que el contrato "
            "**declare** un indicador de trabajo, no que la tool lo **emita**. "
            "`vault_tags` declaraba `total` y `renamed`, que ningún modo devuelve, "
            "y `rebuild`/`rename` escribían sin `write_report()`: el audit en 0 "
            "con una tool que callaba lo que escribía. Lo de `vault_tags` se "
            "arregló; el criterio del audit sigue siendo el declarado. Medido el "
            "2026-10-15."
        ),
        "por_que_no_ahora": (
            "Contrastar lo emitido exige ejecutar cada tool con escritura por el "
            "camino que escribe, sobre un vault desechable y con argumentos "
            "válidos por modo; `vault_smoke` ejecuta un solo ejemplo, casi siempre "
            "de lectura, y solo exige que salga **algún** campo declarado. Es un "
            "banco de ejecución nuevo, no un arreglo del audit. "
            "`tests/test_tags_dice_lo_que_escribe.py::test_limite_declarado_ap37_mide_lo_declarado` "
            "fija el límite. "
            "El 2026-10-16 entró el banco: `vault_noop_audit --ejecutado` ejecuta "
            "el ejemplo de cada tool con side effects sobre la copia de "
            "`vault_smoke` y contrasta el árbol con el envelope. Destapó dos que "
            "escribían callando (`vault_delta --snapshot`, `vault_graph_fix "
            "--apply`; a0fdb0c y 9985e24). Medido ese día: de 92 tools, 17 "
            "medidas y en verde, 2 sin invocación (runtime node) y 73 cuyo "
            "ejemplo no escribe, que el banco no ve. Saldarla exige un ejemplo "
            "de escritura por tool, no otro detector; el modo estático sigue "
            "midiendo lo declarado."
        ),
    },
    {
        "id": "ap48_sin_voz",
        "estado": "saldada",
        "saldada_en": "v41.7 (2026-10-16)",
        "sostenida_por": [
            "tests/test_voice.py::test_ap48_la_pronuncia_la_puerta_que_la_ejecuta",
            "tests/test_vault_onboard.py::test_el_vault_resultante_no_necesita_sanacion",
        ],
        "desde": "tras v41.6",
        "capa": "4",
        "que": (
            "AP-43 sobre AP-48: ninguna tool del catálogo MCP pronuncia AP-48. "
            "Su guard es `vault_mcp_catalog.check_contracts`, que corre la "
            "puerta `contratos` y no es una tool del catálogo, así que la norma "
            "no llega al agente por `vault_says`. Hasta f2110b5 la «pronunciaba» "
            "`vault_norms`, que solo la nombraba en el registro: la afirmación "
            "era falsa y C2 dejó de aceptarla. Medido el 2026-10-15."
        ),
        "por_que_no_ahora": (
            "Darle voz exige que una tool del catálogo ejecute la comprobación "
            "—exponer `vault_mcp_catalog` como tool, o que `vault_gate` publique "
            "las normas de cada puerta desde una función que las mida— y las dos "
            "son decisiones de superficie de producto, no un arreglo. Volver a "
            "atribuírsela a `vault_norms` sería reponer la afirmación falsa. "
            "`tests/test_voice.py::test_limite_declarado_ap48_sin_voz` fija la "
            "muda y falla el día que una tool la pronuncie."
        ),
    },
    {
        "id": "lock_caduca_por_reloj_de_pared",
        "estado": "saldada",
        "saldada_en": "v41.7 (2026-10-16)",
        "sostenida_por": [
            "tests/test_lock_dueno_vivo.py::test_un_salto_del_reloj_no_roba_el_lock_a_un_dueno_vivo",
            "tests/test_lock_dueno_vivo.py::test_un_dueno_muerto_de_la_misma_maquina_se_recupera_sin_esperar",
            "tests/test_lock_dueno_vivo.py::test_un_dueno_de_otra_maquina_sigue_caducando_por_edad",
        ],
        "desde": "v41.6",
        "capa": "5",
        "que": (
            "`vault.kernel.bloqueo.adquirir` da un lock por huérfano cuando "
            "`time.time() - createdAt` supera `CADUCA_TRAS` (120 s), y la edad "
            "sale del reloj de pared, que salta: NTP, una VM que despierta, la "
            "resincronización de WSL. Un salto hacia delante de más de 120 s le "
            "roba el lock a un dueño vivo y dos escritores pisan la misma nota. "
            "Medido el 2026-10-15 con la suite en python:3.9-slim sobre Docker "
            "Desktop: el reloj del contenedor saltó 3458 s y `vault_append` "
            "escribió con ok:true sobre una nota bloqueada "
            "(`test_append_concurrente::"
            "test_con_la_nota_bloqueada_no_escribe_y_lo_dice`)."
        ),
        "por_que_no_ahora": (
            "No es regresión: el criterio es el de siempre, y apareció en la "
            "ronda que sube a v41.6. Arreglarlo es una decisión de diseño: "
            "mirar si el `pid` de `owner.json` vive exige una consulta por "
            "plataforma y no sirve si dos máquinas comparten el vault por una "
            "carpeta sincronizada, y `owner.json` no guarda el host. "
            "`tests/test_lock_caduca_por_reloj_de_pared.py::"
            "test_limite_declarado_lock_caduca_por_reloj_de_pared` fija el "
            "límite y falla el día que un dueño vivo conserve el lock. "
            "(Saldada el 2026-10-15 con el criterio de py-filelock, elegido "
            "por el usuario tras comparar py-filelock, QLockFile, "
            "proper-lockfile, el DynamoDB Lock Client y git: `owner.json` "
            "guarda `maquina` —host y plataforma, porque WSL y Windows "
            "comparten host y no pids— e `inicio` del proceso, y en la misma "
            "máquina el lock solo se rompe si el dueño murió o su pid es ya de "
            "otro; el reloj no interviene. En Windows el pid se consulta con "
            "`OpenProcess`, nunca con `os.kill`, que lo terminaría. Queda "
            "declarado el límite que no tiene arreglo en un lock de ficheros: "
            "un dueño de otra máquina —una carpeta sincronizada— o un "
            "`owner.json` anterior siguen caducando por edad.)"
        ),
    },
]


def _test_existe(ref: str) -> bool:
    """`tests/fichero.py::test_x` existe como función en ese fichero.

    Se mira el AST y no el texto: un nombre en un comentario o en un docstring
    no sostiene nada.
    """
    ruta, _, nombre = ref.partition("::")
    fichero = REPO_ROOT / ruta
    if not nombre or not fichero.is_file():
        return False
    try:
        arbol = ast.parse(fichero.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return False
    return any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nombre
               for n in ast.walk(arbol))


# ── Lectura de los registros (todo por puerto, nada reimplementado) ──────────

def _doc_rel() -> str:
    """Ruta del plano relativa al repo, sin reventar si apunta fuera.

    `relative_to` lanza `ValueError` cuando el destino queda fuera del repo —el
    caso de un test que redirige `DOC` a un temporal—, y un guard que aborta con
    traza en vez de emitir su envelope presenta un fallo propio como si no
    hubiera medida (AP-51).
    """
    try:
        return str(DOC.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(DOC).replace("\\", "/")


def _registros() -> Dict[str, Any]:
    import vault_arch
    import vault_gate
    import vault_mcp_catalog
    import vault_norms
    import vault_servicio

    return {
        "arch": vault_arch,
        "gate": vault_gate,
        "catalog": vault_mcp_catalog,
        "norms": vault_norms,
        "servicio": vault_servicio,
    }


def _leer_baseline() -> Dict[str, Any]:
    if not BASELINE.exists():
        return {"uncovered_norms": []}
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def _test_ejercita(code: str, texto: str) -> bool:
    """¿Ese fichero de tests **ejercita** la norma, o solo la nombra?

    Hasta v40.16 bastaba `code in texto`: un docstring que citaba «AP-21» de
    pasada certificaba la norma como cubierta, y como la baseline de la capa 4
    solo encoge, la certificación era irreversible. Aquí el código tiene que
    aparecer en el **cuerpo** de una función `test_*`, descontado su docstring.

    El límite queda dicho: sigue siendo sintáctico. Un `assert` cuyo mensaje
    menciona la norma cuenta, aunque no la mida. Distingue «nadie la prueba» de
    «alguien la nombró», que es el salto que faltaba; no prueba enforcement.
    """
    if code not in texto:
        return False
    return any(code in s for s in _cuerpos_de_tests(texto))


@lru_cache(maxsize=None)
def _cuerpos_de_tests(texto: str) -> tuple:
    """Cada sentencia de cada `test_*`, sin docstring, ya `unparse`-ada.

    No depende de la norma buscada, así que se calcula una vez por fichero.
    Hasta el 2026-10-15 se parseaba por cada norma: 79 × ~450 ficheros,
    12 de los 26 s de `check()`. Una sentencia por elemento, como antes: la
    búsqueda no puede casar a caballo entre dos.
    """
    try:
        arbol = ast.parse(texto)
    except SyntaxError:
        return ()
    cuerpos = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not nodo.name.startswith("test_"):
            continue
        cuerpo = nodo.body[1:] if ast.get_docstring(nodo) else nodo.body
        cuerpos.extend(ast.unparse(s) for s in cuerpo)
    return tuple(cuerpos)


def cobertura_de_normas() -> List[Dict[str, Any]]:
    """Capa 4: por cada norma, qué puerta la hace cumplir y qué tests la nombran.

    La puerta se deriva de `tools_enforcing`/`tools_detecting` cruzado con el script
    de cada entrada de `PUERTAS`. Es la única unión posible sin inventar un campo
    nuevo en el catálogo de normas — y añadir ese campo sería pedirle a la norma que
    conozca al guard, que es la dependencia al revés.
    """
    r = _registros()
    scripts_de_puerta = {p["cmd"][0][:-3]: p["id"] for p in r["gate"].PUERTAS}
    textos = {
        p.name: p.read_text(encoding="utf-8", errors="replace")
        for p in TESTS_DIR.rglob("*.py")
    }

    filas = []
    for norma in r["norms"].NORM_CATALOG:
        code = norma["code"]
        tools = (
            list(norma.get("tools_enforcing", []))
            + list(norma.get("tools_detecting", []))
            + list(norma.get("tools_del_patron", []))
        )
        # `tools_enforcing` admite entradas con paréntesis explicativo
        # ("vault_section_index (guard CN-02)"): el nombre es el primer token.
        puertas = sorted(
            {
                scripts_de_puerta[t.split()[0]]
                for t in tools
                if t.split() and t.split()[0] in scripts_de_puerta
            }
        )
        tests = sorted(f for f, texto in textos.items() if _test_ejercita(code, texto))
        # Una norma que declara `cobertura_descubierta` no es deuda descubierta
        # por sorpresa: es un hueco escrito, con motivo, y se publica aparte.
        # Mezclarla con las que nadie miró haría que declararse honestamente
        # saliera más caro que callarse.
        motivo = (norma.get("cobertura_descubierta") or "").strip()
        filas.append(
            {
                "code": code,
                "name": norma["name"],
                "enforcement": norma["enforcement"],
                "gates": puertas,
                "tests": tests,
                "covered": bool(puertas or tests),
                "uncovered_declared": motivo or None,
            }
        )
    return filas


def capas() -> Dict[str, Any]:
    """Las siete capas del plano, cada una derivada de su registro."""
    r = _registros()
    servicio = r["servicio"]
    traza = servicio.trazabilidad()
    cobertura = cobertura_de_normas()
    sin_hogar = r["arch"].modulos_sin_hogar()

    tools_por_grupo: Dict[str, int] = {}
    for fila in traza:
        tools_por_grupo[fila["group"]] = tools_por_grupo.get(fila["group"], 0) + 1

    return {
        "1_servicio": servicio.SERVICIO,
        "2_capacidades": {
            nombre: {
                "titulo": datos["titulo"],
                "resultado": datos["resultado"],
                "nota": datos.get("nota"),
                "grupos": sorted(datos["grupos"]),
                "tools": sum(
                    1 for f in traza if f["capability"] == nombre
                ),
            }
            for nombre, datos in servicio.CAPACIDADES.items()
        },
        "3_contextos": {
            ctx: {
                "titulo": datos["titulo"],
                "puertos": len(datos["puertos"]),
                "modulos": len(datos["modulos"]),
                "prohibe": datos["prohibe"],
                # Puente de ADR-0002 (deuda #12): módulos del contexto que no
                # importan nada de `vault/<ctx>/`. Va dentro de la capa —es una
                # cifra de contextos— y no como capa propia, que rompería las siete.
                "sin_hogar": sum(1 for m in sin_hogar if r["arch"].contexto_de(m) == ctx),
            }
            for ctx, datos in r["arch"].CONTEXTS.items()
        },
        "4_normas": cobertura,
        "5_tools": {
            "total": len(traza),
            "grupos": len(tools_por_grupo),
            "por_grupo": dict(sorted(tools_por_grupo.items())),
        },
        "6_trazabilidad": traza,
        "7_deuda": DEUDA_DECLARADA,
    }


# ── El plano ─────────────────────────────────────────────────────────────────

def blueprint(c: Optional[Dict[str, Any]] = None) -> str:
    """El plano en Markdown. `c` lo pasa quien ya calculó las capas (AP-66)."""
    r = _registros()
    c = capas() if c is None else c
    lineas: List[str] = []
    A = lineas.append

    A("# Plano de construcción del estándar")
    A("")
    A("> **Documento derivado. No se edita a mano.**")
    A("> Se regenera con `python scripts/vault_blueprint.py --blueprint` y una puerta")
    A("> falla si diverge de los registros (`--check --strict`). El papel manda porque")
    A("> lo escribe el código: si alguna cifra de aquí se teclea, deja de ser un plano y")
    A("> pasa a ser una opinión con formato de tabla.")
    A("")
    A("La jerarquía va de arriba abajo: el servicio justifica las capacidades, las")
    A("capacidades agrupan las tools, los contextos dicen dónde vive cada una y por dónde")
    A("se habla con ella, las normas dicen qué no puede pasar y las puertas lo impiden.")
    A("Cada capa nombra el registro del que sale — ninguna capa es prosa.")
    A("")

    # ── Capa 1 ──
    s = c["1_servicio"]
    A("## Capa 1 — Servicio de negocio")
    A("")
    A("*Registro: `vault_servicio.SERVICIO`*")
    A("")
    A(f"**{s['titulo']}**")
    A("")
    A(s["declaracion"])
    A("")
    A("Restricciones que son decisión de producto, no limitación pendiente:")
    A("")
    A("| Restricción | Por qué | Declarada en |")
    A("|---|---|---|")
    for rest in s["restricciones"]:
        A(f"| {rest['texto']} | {rest['motivo']} | `{rest['declarada_en']}` |")
    A("")

    # ── Capa 2 ──
    A("## Capa 2 — Capacidades → grupos")
    A("")
    A("*Registro: `vault_servicio.CAPACIDADES` + `vault_mcp_catalog.mapa_de_grupos()`*")
    A("")
    A("| Capacidad | Resultado | Grupos | Tools |")
    A("|---|---|---|---|")
    for nombre, datos in c["2_capacidades"].items():
        grupos = ", ".join(str(g) for g in datos["grupos"])
        A(f"| **{datos['titulo']}** (`{nombre}`) | {datos['resultado']} | {grupos} | {datos['tools']} |")
    A("")
    for nombre, datos in c["2_capacidades"].items():
        if datos.get("nota"):
            A(f"- **`{nombre}`** — {datos['nota']}")
    A("")
    A("Guard: todo grupo del catálogo pertenece a exactamente una capacidad y toda")
    A("capacidad tiene al menos una tool viva (`vault_servicio.py --check --strict`).")
    A("")

    # ── Capa 3 ──
    A("## Capa 3 — Contextos acotados → puertos")
    A("")
    A("*Registro: `vault_arch.CONTEXTS`. El detalle de puertos y cruces vive en")
    A("[`docs/ARQUITECTURA.md`](./ARQUITECTURA.md), que no se absorbe aquí: son dos")
    A("documentos con dos sujetos, y fundirlos habría hecho un solo documento que nadie")
    A("regenera.*")
    A("")
    A("| Contexto | Puertos | Módulos | Sin hogar | Prohíbe |")
    A("|---|---|---|---|")
    for ctx, datos in c["3_contextos"].items():
        prohibe = "; ".join(datos["prohibe"]) or "—"
        A(f"| **{datos['titulo']}** (`{ctx}`) | {datos['puertos']} | {datos['modulos']} | {datos['sin_hogar']} | {prohibe} |")
    A("")
    A(f"**Puente de ADR-0002:** {sum(d['sin_hogar'] for d in c['3_contextos'].values())} módulos de `scripts/` no importan "
      "nada de `vault/<su contexto>/` (`vault_arch.modulos_sin_hogar`). La cifra solo "
      "encoge: un módulo nuevo sin hogar bloquea `vault_arch --check`. Importar del "
      "contexto es empezar a delegar, no haber migrado.")
    A("")

    # ── Capa 4 ──
    cobertura = c["4_normas"]
    cubiertas = [n for n in cobertura if n["covered"]]
    descubiertas = [n for n in cobertura if not n["covered"]]
    A("## Capa 4 — Normas → puertas → tests")
    A("")
    A("*Registros: `vault_norms.NORM_CATALOG` + `vault_gate.PUERTAS` + `tests/`*")
    A("")
    A(f"{len(cubiertas)} de {len(cobertura)} normas tienen puerta o test que las nombre.")
    A("**Es la única capa con baseline**, y por un motivo concreto: las demás se midieron")
    A("en cero el día que se declararon porque sus datos ya existían y solo faltaba")
    A("atarlos. Ésta no. Exigir cero aquí el primer día habría hecho nacer la puerta en")
    A("rojo, y una puerta en rojo se desactiva.")
    A("")
    A("| Norma | Enforcement | Puertas | Tests |")
    A("|---|---|---|---|")
    for n in cobertura:
        puertas = ", ".join(f"`{p}`" for p in n["gates"]) or "—"
        tests = ", ".join(f"`{t}`" for t in n["tests"]) or "—"
        A(f"| **{n['code']}** — {n['name']} | {n['enforcement']} | {puertas} | {tests} |")
    A("")
    if descubiertas:
        A(f"Sin puerta ni test ({len(descubiertas)}): " + ", ".join(
            f"`{n['code']}`" for n in descubiertas
        ) + ".")
        A("")

    # ── Capa 5 ──
    A("## Capa 5 — Tools → grupos → contrato")
    A("")
    A("*Registros: `vault_mcp_catalog.TOOLS_CATALOG` + `<vault>/00_System/tool-spec.json`*")
    A("")
    A(f"{c['5_tools']['total']} tools activas en {c['5_tools']['grupos']} grupos. Toda tool")
    A("del catálogo tiene entrada de contrato y toda entrada sin catálogo declara")
    A("`status: archived | internal | orphan` — no se borra, se anota")
    A("(`vault_mcp_catalog.py --check-contracts`).")
    A("")
    A("| Grupo | Tools |")
    A("|---|---|")
    for grupo, n in c["5_tools"]["por_grupo"].items():
        A(f"| {grupo} | {n} |")
    A("")

    # ── Capa 6 ──
    A("## Capa 6 — Trazabilidad")
    A("")
    A("*Derivada de las capas anteriores: `tool → grupo → capacidad → servicio`*")
    A("")
    A("Una tool sin capacidad no tiene contra qué justificarse, y es así como un catálogo")
    A("crece por acumulación. La cadena se exige entera: si un eslabón falta, la puerta")
    A("falla — no se rellena con el valor más cercano.")
    A("")
    A("| Tool | Grupo | Capacidad |")
    A("|---|---|---|")
    for fila in c["6_trazabilidad"]:
        A(f"| `{fila['tool']}` | {fila['group_id']} — {fila['group']} | {fila['capability']} |")
    A("")

    # ── Capa 7 ──
    A("## Capa 7 — Deuda viva")
    A("")
    A("*Registro: `vault_blueprint.DEUDA_DECLARADA` + las baselines de `scripts/`*")
    A("")
    A("Deuda **declarada**: conocida, medida y con motivo escrito de por qué no se ataca")
    A("todavía. Lo que no está aquí no es que no exista — es que nadie lo ha medido, que")
    A("es una situación distinta y peor.")
    A("")
    pendientes = sum(1 for d in c["7_deuda"] if d.get("estado") == "pendiente")
    A(f"**{pendientes} pendientes** de {len(c['7_deuda'])} declaradas. Una deuda saldada no")
    A("desaparece de la tabla: se queda con `estado: saldada` y la versión que la cerró,")
    A("porque una entrada borrada no se distingue de una que nadie volvió a mirar.")
    A("")
    A("| Deuda | Estado | Desde | Capa | Qué | Por qué no ahora |")
    A("|---|---|---|---|---|---|")
    for d in c["7_deuda"]:
        estado = d.get("estado", "—")
        if d.get("saldada_en"):
            estado = f"{estado} en {d['saldada_en']}"
        A(f"| `{d['id']}` | {estado} | {d.get('desde', '—')} "
          f"| {d['capa']} | {d['que']} | {d['por_que_no_ahora']} |")
    A("")
    A("| Baseline | Norma | Congelado | Objetivo | Pendiente |")
    A("|---|---|---|---|---|")
    presentes = [(SCRIPTS_DIR / f, c, n) for f, c, n in _BASELINES
                 if (SCRIPTS_DIR / f).exists()]
    # Todas las pendientes de una vez: dos procesos de git, no tres por fila.
    for (ruta, clave, norma), p in zip(presentes, vault_baseline.pendientes(presentes)):
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        total = _congelado(datos.get(clave))
        A(f"| `scripts/{ruta.name}` | {norma} | {total} | {_objetivo(ruta, clave, norma)} "
          f"| {_celda_pendiente(p)} |")
    A("")
    A("Todas encogen y ninguna crece sin decirlo: los tres audits con baseline indexan")
    A("por firma de sitio —`módulo::función::hash de `ast.unparse``— así que mover un")
    A("sitio ya no lo estrena como deuda nueva, y `--freeze` se niega a congelar lo que")
    A("no tiene precedente salvo con `--admitir-nuevos`, que además lo lista.")
    A("")
    A("Las dos últimas columnas son de v40.24 y no dicen lo mismo. **Objetivo** es un")
    A("compromiso escrito —a cuánto debe encoger, para cuándo, con qué cadencia y quién")
    A("lo revisa— y `sin objetivo` se publica como tal en vez de leerse como cumplido:")
    A("no comprometerse no puede salir más barato que comprometerse. **Pendiente** no se")
    A("escribe en ninguna parte: sale de `git log` sobre el propio fichero cada vez que")
    A("se genera este plano, porque una pendiente escrita a mano sería una afirmación")
    A("sobre la historia sin que git la respalde (AP-53).")
    A("")
    A("---")
    A("")
    A(f"*{len(r['gate'].PUERTAS)} puertas de cierre. Generado por "
      "`scripts/vault_blueprint.py`.*")
    return "\n".join(lineas) + "\n"


def _objetivo(ruta: Path, clave: str, norma: str) -> str:
    """La celda de `Objetivo`, pedida al dueño del contrato (`vault_baseline`).

    El plano no decide qué es un objetivo válido: eso lo dice `vault_baseline`,
    igual que los puertos rotos los dice `vault_arch`. Un plano que midiera por
    su cuenta sería AP-05 con formato de tabla.
    """
    e = vault_baseline.estado_objetivo(ruta, clave, norma)
    if e["estado"] == "sin_objetivo":
        return "— *sin objetivo*"
    if e["estado"] == "no_aplica":
        return f"— *no aplica*: {e['motivo']}"
    if e["estado"] == "objetivo_invalido":
        return "⚠ inválido: " + "; ".join(e["problemas"])
    o = e["objetivo"]
    return (f"≤ {o['tamano']} para {o['fecha_limite']} · cada "
            f"{o['cadencia_dias']} d · {o['dueno']} → **{e['estado']}**")


def _pendiente(ruta: Path, clave: str, norma: str) -> str:
    """La celda de `Pendiente`: derivada de git, nunca escrita en el fichero."""
    return _celda_pendiente(vault_baseline.pendiente(ruta, clave, norma))


def _celda_pendiente(p: Dict[str, Any]) -> str:
    """La celda a partir de la pendiente ya derivada (`vault_baseline.pendientes`)."""
    if not p["disponible"]:
        return "— *sin historia de git*"
    if p["muestras"] < 2:
        return f"— *{p['muestras']} muestra*"
    serie = " → ".join(str(x["tamano"]) for x in p["serie"][-6:])
    return f"{serie} ({p['sentido']}, Δ{p['delta']:+d})"


def _congelado(valor: Any) -> Any:
    """superseded_by: vault_baseline.tamano_congelado (v40.24).

    El cuerpo estaba aquí y `estado_objetivo` lo necesitaba también; dos sitios
    decidiendo cuántos elementos congela un dict de listas es AP-57 en el plano
    que publica AP-57. Se conserva la función porque la llama el generador.
    """
    return vault_baseline.tamano_congelado(valor)


#: Las baselines del repo, con la clave donde vive la lista y la norma que sostienen.
#: Toda `scripts/*baseline*.json` aparece aquí — el guard lo comprueba. Tres
#: faltaban hasta v40.16 y la capa 6 las publicaba como si no existieran: una
#: deuda congelada que el plano no lista es una deuda que nadie revisa.
_BASELINES = [
    ("arch-baseline.json", "crossings", "cruces entre contextos"),
    ("arch-baseline.json", "off_port_crossings", "cruces fuera de puerto"),
    ("blame-baseline.json", "sites", "AP-51"),
    ("error-contract-baseline.json", "sites", "AP-52"),
    ("noop-baseline.json", "tools", "AP-37"),
    ("smoke-baseline.json", "failing", "AP-42"),
    ("blueprint-baseline.json", "uncovered_norms", "capa 4 — norma sin puerta ni test"),
    ("criterios-baseline.json", "sitios", "AP-57"),
    ("ciclos-baseline.json", "sitios", "AP-58 — ciclo esquivado con import diferido"),
    ("kernel-baseline.json", "sitios", "AP-59 — núcleo declarado sin contraste"),
    ("norms-distincion-baseline.json", "normas",
     "AP-60 — normas que no declaran de qué se distinguen"),
    ("norms-coherence-baseline.json", "claims", "AP-55 — C2, afirmación sin traza"),
    ("field-compat-baseline.json", "stable", "contrato de campos con los consumidores"),
    ("excepcion-declarada-baseline.json", "sitios",
     "AP-61 — la excepción declarada no es la que escapa"),
    ("recursos-baseline.json", "sitios",
     "AP-62 — el consumidor cruza para leer un recurso y paga el fan-out"),
]


# ── Guards ───────────────────────────────────────────────────────────────────

def _sin_cobertura(cobertura: Optional[List[Dict[str, Any]]] = None) -> set:
    """Normas sin puerta ni test, **descontadas las que lo declaran por escrito**.

    Una norma con `cobertura_descubierta` es un hueco escrito y con motivo, y la
    capa 4 ya lo publica en su propia columna. Contarla también como deuda haría
    que declararse honestamente saliera más caro que callarse — que es como
    AP-04 apareció aquí el día que la cobertura por mención dejó de valer.
    """
    return {
        n["code"] for n in (cobertura_de_normas() if cobertura is None else cobertura)
        if not n["covered"] and not n["uncovered_declared"]
    }


#: Forma de `saldada_en`: la versión que la cerró, con fecha opcional, o
#: «tras vN.N (fecha, …)» cuando se cerró sin versión publicada todavía.
FORMA_DE_SALDADA_EN = re.compile(
    r"^(tras )?v\d+\.\d+( \(\d{4}-\d{2}-\d{2}[^)]*\))?$")


def check(strict: bool = False) -> Dict[str, Any]:
    r = _registros()
    problemas: List[Dict[str, str]] = []
    # AP-66: la capa 4 lee todos los tests; el plano y la baseline la comparten.
    c = capas()

    # 1. El doc publicado no diverge de los registros.
    if not DOC.exists():
        problemas.append(
            {"kind": "plano_ausente", "detail": "docs/BLUEPRINT.md no existe — "
             "genera con `python scripts/vault_blueprint.py --blueprint`"}
        )
    elif DOC.read_text(encoding="utf-8").strip() != blueprint(c).strip():
        problemas.append(
            {"kind": "plano_desactualizado", "detail": "docs/BLUEPRINT.md difiere de "
             "los registros — regenera con `--blueprint`. Si el cambio se escribió a "
             "mano en el doc, se pierde: el registro es la fuente"}
        )

    # 2. Las capas 2, 3 y 5 delegan en el guard de su registro. No se remide.
    traza = r["servicio"].check()
    if not traza["ok"]:
        problemas.append(
            {"kind": "trazabilidad_rota",
             "detail": f"vault_servicio --check falla: {traza['orphan_groups']} "
                       f"{traza['unknown_groups']} {traza['empty_capabilities']}"}
        )
    rotos = r["arch"].puertos_rotos()
    if rotos:
        problemas.append(
            {"kind": "puertos_rotos", "detail": f"{len(rotos)} puertos apuntan a un "
             "símbolo que no existe (`vault_arch --check`)"}
        )

    # 3. Capa 4 contra la baseline: solo puede encoger.
    base = set(_leer_baseline().get("uncovered_norms", []))
    descubiertas = _sin_cobertura(c["4_normas"])
    nuevas = sorted(descubiertas - base)
    saldadas = sorted(base - descubiertas)
    if nuevas:
        problemas.append(
            {"kind": "norma_sin_puerta_ni_test", "detail": ", ".join(nuevas)}
        )

    # 3.b Ninguna baseline queda fuera de la capa 6. Una deuda congelada que el
    #     plano no publica es deuda que nadie revisa — y las tres que faltaban
    #     (AP-57, C2 de AP-55, contrato de campos) llevaban desde su estreno.
    listadas = {f for f, _clave, _norma in _BASELINES}
    for ruta in sorted(SCRIPTS_DIR.glob("*baseline*.json")):
        if ruta.name not in listadas:
            problemas.append(
                {"kind": "baseline_no_publicada",
                 "detail": f"{ruta.name} congela deuda y no aparece en "
                           "`vault_blueprint._BASELINES`: la capa 6 la omite"}
            )

    # 4. Toda deuda declarada dice en qué estado está y desde cuándo. Sin esto,
    #    «pendiente» sería una propiedad implícita de aparecer en la lista, y una
    #    propiedad implícita no la comprueba nadie: el día que una se salde, la
    #    forma cómoda de anotarlo es borrarla, y ahí el registro deja de servir.
    for d in DEUDA_DECLARADA:
        estado = d.get("estado")
        if estado not in ESTADOS_DE_DEUDA:
            problemas.append(
                {"kind": "deuda_sin_estado",
                 "detail": f"{d['id']}: estado {estado!r} no está en "
                           f"{list(ESTADOS_DE_DEUDA)}"}
            )
        if not (d.get("desde") or "").strip():
            problemas.append(
                {"kind": "deuda_sin_version",
                 "detail": f"{d['id']}: no dice desde qué versión se arrastra"}
            )
        # El comentario de `ESTADOS_DE_DEUDA` prometía desde v40.x que una deuda
        # saldada «se conserva con la versión que la cerró», y nada lo exigía:
        # no había ninguna saldada todavía, así que la promesa nunca se probó.
        # `saldada` sin versión es indistinguible de un `pendiente` que alguien
        # marcó y no fechó — que es la forma cómoda de dar por cerrado sin
        # poder citar dónde.
        if estado == "saldada" and not (d.get("saldada_en") or "").strip():
            problemas.append(
                {"kind": "deuda_saldada_sin_version",
                 "detail": f"{d['id']}: saldada sin `saldada_en`"}
            )
        # No vacío no basta: el test que cruza `saldada_en` con el changelog se
        # salta lo que no encuentra, así que texto libre pasaba los dos.
        elif d.get("saldada_en") is not None and not FORMA_DE_SALDADA_EN.match(d["saldada_en"]):
            problemas.append(
                {"kind": "deuda_saldada_en_sin_forma",
                 "detail": f"{d['id']}: `saldada_en` {d['saldada_en']!r} no es "
                           f"«vN.N», «vN.N (AAAA-MM-DD…)» ni «tras vN.N (…)»"}
            )
        # La versión dice cuándo; el test dice que sigue siendo verdad. Sin él,
        # `saldada` es una afirmación que nada vuelve a comprobar, y la
        # dirección contraria también pasó: dos entradas siguieron `pendiente`
        # desde v40.23 porque ninguna saldada apuntaba a su prueba.
        if estado == "saldada":
            refs = d.get("sostenida_por") or []
            rotas = [r for r in refs if not _test_existe(r)]
            if not refs or rotas:
                problemas.append(
                    {"kind": "deuda_saldada_sin_sosten",
                     "detail": f"{d['id']}: " + (
                         f"`sostenida_por` apunta a tests que no existen: {rotas}"
                         if rotas else "saldada sin `sostenida_por`")}
                )

    ok = not problemas
    resultado = {
        "ok": ok,
        "tool": "vault_blueprint",
        "action": "check",
        "layers": 7,
        "doc": _doc_rel(),
        "norms_total": len(r["norms"].NORM_CATALOG),
        "norms_uncovered": len(descubiertas),
        "norms_uncovered_baseline": len(base),
        "new_uncovered_norms": nuevas,
        "settled_uncovered_norms": saldadas,
        "declared_debt": len(DEUDA_DECLARADA),
        # Publicado por separado y no solo como total: el número de deudas
        # declaradas baja igual si una se salda que si alguien la borra, así que
        # por sí solo no dice nada. Lo que se lee es cuántas siguen vivas.
        "declared_debt_pending": sum(
            1 for d in DEUDA_DECLARADA if d.get("estado") == "pendiente"),
        "declared_debt_settled": sorted(
            d["id"] for d in DEUDA_DECLARADA if d.get("estado") == "saldada"),
        "problems": problemas,
        "hint": (
            "Una norma nueva sin puerta ni test no se congela: se le escribe el test. "
            "La baseline existe para la deuda que ya estaba, no para la que entra hoy."
        ),
    }
    if strict and not ok:
        resultado["exit_code"] = 1
    return resultado


def freeze(admitir_nuevos: bool = False) -> Dict[str, Any]:
    """Congela la deuda de la capa 4. Se niega a estrenar deuda sin `--admitir-nuevos`.

    Mismo contrato que los tres audits desde v40.6, y por el mismo motivo: un
    `--freeze` que acepta cualquier cosa convierte la baseline en un registro de lo
    que hay, que es lo contrario de un techo.
    """
    base = set(_leer_baseline().get("uncovered_norms", []))
    descubiertas = _sin_cobertura()
    nuevas = sorted(descubiertas - base)
    if nuevas and not admitir_nuevos:
        salida = emit_error(
            "vault_blueprint",
            "DEBT_WOULD_GROW",
            f"{len(nuevas)} normas sin puerta ni test que no estaban congeladas: "
            + ", ".join(nuevas),
        )
        salida["new_uncovered_norms"] = nuevas
        return salida

    vault_baseline.escribir(
        BASELINE, "uncovered_norms", "capa 4 del plano",
        "Normas sin puerta que las haga cumplir ni test que las nombre. "
        "Indexada por código de norma. Esta lista solo puede ENCOGER: una "
        "norma nueva sin cobertura no se congela, se le escribe el test.",
        sorted(descubiertas), extra={"norm": "capa 4 del plano"},
    )
    return {
        "ok": True,
        "tool": "vault_blueprint",
        "action": "freeze",
        "uncovered_norms": len(descubiertas),
        "admitted_new": nuevas if admitir_nuevos else [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plano de construcción: registros atados y verificados"
    , allow_abbrev=False)
    parser.add_argument("--blueprint", action="store_true", help="regenera docs/BLUEPRINT.md")
    parser.add_argument("--check", action="store_true", help="el doc y la trazabilidad")
    parser.add_argument("--strict", action="store_true", help="exit 1 si falla")
    parser.add_argument("--freeze", action="store_true", help="congela la deuda de la capa 4")
    parser.add_argument(
        "--admitir-nuevos", action="store_true",
        help="permite congelar normas sin cobertura que no tenían precedente",
    )
    parser.add_argument("--layers", action="store_true", help="las 7 capas en JSON")
    args = parser.parse_args()

    if args.blueprint:
        DOC.parent.mkdir(parents=True, exist_ok=True)
        texto = blueprint()
        # AP-37: `changed` distingue «regeneré el plano» de «el plano ya estaba
        # al día». Sin ese dato, una regeneración que no toca nada y otra que
        # reescribe el documento entero devuelven el mismo `ok: true`, y quien
        # llama no puede saber cuál de las dos ocurrió.
        anterior = DOC.read_text(encoding="utf-8") if DOC.exists() else None
        DOC.write_bytes(texto.encode("utf-8"))
        salida: Dict[str, Any] = {
            "ok": True,
            "tool": "vault_blueprint",
            "action": "blueprint",
            "doc": _doc_rel(),
            "changed": 0 if anterior == texto else 1,
            "lines": texto.count("\n"),
        }
    elif args.freeze:
        salida = freeze(admitir_nuevos=args.admitir_nuevos)
    elif args.layers:
        salida = {"ok": True, "tool": "vault_blueprint", "layers": capas()}
    else:
        salida = check(strict=args.strict)

    print(json.dumps(salida, indent=2, ensure_ascii=False))
    return 1 if (args.strict and not salida.get("ok")) else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_blueprint"))
