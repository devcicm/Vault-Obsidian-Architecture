R1B-CIERRE — Entorno, procedimiento e incidentes — 2026-10-25
==============================================================

TASK_ID: CIERRE RONDA 1B (H-QA-01 a H-QA-05)
COMMIT_SHA: f24a9b82913294dd3295058a5b56361cc2af229f (fix AP-37)
ENVIRONMENT: Windows, PowerShell 5, Python 3.14.3; worktree aislado
  (<TEMP>/opencode/vault-r1b-iso) con sandbox propio; variables heredadas
  retiradas (VAULT_ROOT/VAULT_STRICT_ROOT/VAULT_MASTER/VAULT_AGENT/PYTHONPATH)
  y TEMP/TMP propio de la corrida.
EXPECTED: gates 26/26 exit 0; arch estricta con invariantes; suite 0 failed.
ACTUAL: gates 26/26 exit 0; arch exit 0 con invariantes; suite 6141 passed,
  0 failed, 11 skipped, exit 0.
EVIDENCE_PATH: R1B-CIERRE-gates.txt, R1B-CIERRE-arch.txt, R1B-CIERRE-suite.txt,
  R1B-CIERRE-AP37-antes.txt, R1B-CIERRE-AP37-despues.txt
CONCLUSION: criterios de cierre tecnico cumplidos sobre entorno limpio y
  reproducible.

PROCEDIMIENTO CANONICO DESCUBIERTO (lo que hace que las 26 puertas den verde en
limpio, no una receta ad hoc)
------------------------------------------------------------------------------
El repo trae su propio reconstructor canonico del runtime de pruebas:
`python tests/sandbox_fixture.py --bootstrap` (tests/sandbox_fixture.py).
Lee el contrato versionado (`vault-sandbox/00_System/tool-spec.json`, TRACKED),
ejecuta `vault_init --no-audit`, siembra notas deterministas —incluidas las
`fixture-incomplete-*.md` de 07_Knowledge que los sanadores necesitan— y genera
los artefactos derivados verificando su presencia. `--check` confirma el estado
"ready". Con el sandbox ready, la suite NO toma propiedad ni lo limpia al
terminar (tests/conftest.py: pytest_sessionfinish solo limpia lo que bootstrapeo),
de modo que gates -> arquitectura -> suite miden el mismo entorno y SHA.
Verificado: `--check` da exit 0 tambien DESPUES de la suite.

INCIDENTES DEL CIERRE (documentados, no ocultos)
-------------------------------------------------
PASADA 1 — gates 21/26 + suite INTERNALERROR.
  Causa: la reconstruccion uso `vault_standard_upgrade --to v41.23` tras borrar
  el sandbox COMPLETO. Pero `00_System/tool-spec.json` esta VERSIONADO en git y
  ese comando no lo recrea: el bootstrap de la suite lanzo FileNotFoundError al
  leer su spec canonica (tests/sandbox_fixture.py:115) y cinco puertas cayeron
  en cascada (contratos, conteos, noop, campos, doc_staleness).
  Correccion: restaurar el contrato desde git y reconstruir con su dueño.

PASADA 2 — gates 21/26 + suite 8 failed.
  Causa: restaure el contrato con `vault_manifest --bootstrap` (la tool avisa
  que --sync-version no crea la spec). El bootstrap genera una spec de
  INTROSPECCION fresca (159 activas), no el contrato curado y versionado que el
  repo espera (126 + archivados + campos sustituidos): todos los tests de
  contrato de campos y el gate contratos la rechazaron, con razon.
  Correccion: la version del fichero es la de git. `git checkout --`.

PASADA 3 — gates 23/26 + suite 8 failed.
  Causa doble: (a) fije VAULT_ROOT para toda la corrida y con la variable puesta
  caen los tests que EJERCITAN la deteccion
  (test_arquitectura: test_un_paquete_python_no_se_confunde_con_un_vault,
  test_deshacer_el_override_vuelve_al_vault_detectado; test_vault_containment),
  porque miden el comportamiento SIN variable; (b) el orden gates-antes-de-suite
  con un sandbox no-ready hizo que la suite lo reconstruyera y limpiara, y las
  puertas contadas despues vieron el estado limpiado (doc_staleness missing 7).
  Correccion: entorno limpio (sin VAULT_ROOT) y orden canonico bootstrap ->
  gates -> arch -> suite, con el sandbox ready de antemano.

PASADA 4 — VERDE COMPLETO (gates 26/26, arch ok, suite 0 failed, sandbox ready
  antes y despues).

HECHO OBSERVADO vs HIPOTESIS
-----------------------------
- HECHO: el estado del sandbox es una variable real del entorno de validacion;
  un sandbox v41.23 recien reconstruido SIN el bootstrap canonico deja la puerta
  noop (AP-37) y doc_staleness en rojo.
- HECHO: el fix AP-37 (declarar la precondicion del ejemplo en
  FICHEROS_DEL_EJEMPLO) hace que la puerta noop pase en banco limpio con
  escritura real de la tool (R1B-CIERRE-AP37-antes/despues.txt).
- LIMITACION: la matriz de CI (3.9-3.12, ubuntu/macos) sigue sin ejecutarse
  (ver R1B-CIERRE-ci.txt); la validacion de esta ronda es local en Windows y
  Python 3.14.3.