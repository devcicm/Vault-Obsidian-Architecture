# Los carriles: qué se corre, cuándo y qué bloquea

> **Derivado.** Sale de `vault.meta_toolkit.estandar.carriles.CARRILES` y de
> `vault_gate.PUERTAS`; se regenera con `python scripts/vault_gate.py --fix-doc`
> y `--check-doc` falla si diverge. El porqué está en el docstring del registro.

| Carril | Cuándo | Bloquea | Dónde | Presupuesto |
|---|---|---|---|---|
| `dev` | cada cambio en una rama de trabajo, antes de su commit | el commit en la rama de trabajo | local | ≤ 120 s |
| `merge` | antes de integrar una rama en main | la integración en main | local, en serie: puertas y suite comparten vault-sandbox/ | el de vault_metricas: puertas_duracion_s + suite_duracion_s |
| `release` | al etiquetar una versión (tag v*) | la publicación del release | CI: .github/workflows/release.yml | el de la CI; no lo paga el desarrollo |

## `dev`

1. tests que alcanzan a lo que se va a commitear, sin los módulos lentos del perfil salvo el test editado (cae a la suite entera si no hay subconjunto honesto, y lo dice): `python scripts/vault_test_scope.py --changed --correr`
2. puertas de nivel rapida: `python scripts/vault_gate.py --strict --nivel rapida`

Puertas del nivel `rapida` (26): `framework`, `catalogo`, `contratos`, `conteos`, `doc_sync`, `blame`, `contrato_error`, `campos`, `changelog`, `arquitectura`, `servicio`, `blueprint`, `norms_coherence`, `criterios`, `fuente_unica`, `ciclos`, `clones`, `kernel`, `excepcion_declarada`, `recursos`, `procesos_git`, `tests_higiene`, `produccion`, `esquemas`, `metricas`, `doc_staleness`.

## `merge`

1. todas las puertas: `python scripts/vault_gate.py --strict --nivel todas`
2. la suite completa: `python -m pytest tests/ -q -n 4 --tb=short -p no:cacheprovider`

Puertas del nivel `todas` (28): `framework`, `catalogo`, `contratos`, `conteos`, `doc_sync`, `toolkit_audit`, `noop`, `blame`, `contrato_error`, `campos`, `changelog`, `arquitectura`, `servicio`, `blueprint`, `norms_coherence`, `criterios`, `fuente_unica`, `ciclos`, `clones`, `kernel`, `excepcion_declarada`, `recursos`, `procesos_git`, `tests_higiene`, `produccion`, `esquemas`, `metricas`, `doc_staleness`.

## `release`

Exige antes el carril `merge`.

1. el tag es el candidato autorizado de audits/fase2/CANDIDATO-RELEASE.yaml: (lo comprueba la CI)
2. puertas de producto sobre la wheel instalada: `python tests/run_product_gates.py`
3. SBOM e inventario de licencias: `python empaquetado/sbom.py --inventario`
4. recibos del colector QG sobre el product_sha: `python audits/fase2/colector_qg.py --sha <product_sha> --ejecutar --recibos qg-recibos --json qg-informe.json` — cableado en `release.yml`; **falta la primera corrida real**, deuda `colector_qg_sin_primera_corrida`
