# Estado de entrega: ronda workspace-miniserver

Rama `05_tmp/workspace_miniserver` sobre `main` `a2e70827`: 72 commits, subidos solo a esa rama de
trabajo. **No es un release certificado**: merge a `main`, CI, tag y publicación son decisiones del
propietario. Registro inmutable de la ronda (2026-11-10 a 2026-11-23); el detalle día a día vive en el
vault de desarrollo (`vault dev codex`, `19_Audits/` y `18_Bugs/`).

## Validación final

**Pendiente.** La corrida final sobre el HEAD de la rama se canceló al 15 % por falta de crédito
(2026-11-23); no hay veredicto de suite completa sobre este HEAD. Cada commit sí pasó sus tests
focalizados, las 27 puertas rápidas y archify, y los de riesgo real su revisión RDD y un verificador
independiente. Para cerrarla, en un clon limpio del HEAD y sin otra corrida pesada en paralelo:
`python -m pytest tests/ -q -n 2`, `python scripts/vault_gate.py --strict` (incluye `toolkit_audit` y
`noop`), `python scripts/vault_reindex.py --check-indices`, y después Linux 3.9/3.12 y el dictamen QA.

## Hecho, por frente

| Frente | Commits | Resultado verificable |
|---|---|---|
| Aislamiento y contratos | `76657573` `9964d598` `4a6cf371` `d0a7c84e` `af5884b1` `2629f2f8` | Cada tool corre en un proceso contenido (Job en Windows, subreaper en Linux); política de mutación ilegible detiene la escritura; contrato v42 opt-in; requisitos reproducibles desde el change-log |
| Reparación de flujos (13 rotos) | `ac51d973` `b94c6f29` `5e808b8b` `761df59a` `3f22b1fc` `50698e72` `6cf0960b` `39b6a479` `045d3142` `c93e6e02` | Papelera, rollback, patrones, requisitos y proyectos con RED/GREEN |
| Portabilidad para terceros | `4410f84d` `94f57657` `6639e14e` `b32dd73f` `5a521542` `0e2bed50` | Sin rutas de esta máquina ni python fijo; recorrido de tercero 27/27; paridad CLI/MCP |
| ISO (edición 2023) | `7e22c4be` `188129a5` `57ef5c50` `feabb113` `1b24ed31` | 31 normas ISO en el registro (eran 20); fechas de revisión en UTC |
| Big-O e inmutabilidad | `512b037d` `ef4a0a46` | Contexto solo con lo vigente; log append-only: 50 000 entradas de 15,2 s a 1,86 s por escritura |
| Producto usable | `04a9193c` `d7ff66a5` `e941d3ee` | Búsqueda con lo vigente; tutorial ejecutado por test; autoría de commits configurable; docs sin promesas falsas (macOS, MCP sin autenticación) y cifras de su registro |
| Change-log desde el vault nuevo | `e259f661` `9e9c06a2` | El log nace con el vault; `move-log.json` congelado y unificado |
| Nota escalonada (AP-79) | `df3d5c1f` `6ebade39` `5672ad33` `f8e2c294` `0e17c6ee` `da462107` | Notas con lead 0 % -> 100 %; mediana 29 -> 70 palabras; salud 100 sin huérfanas |
| Brownfield del propio repo | `78175bd3` `9085ba17` `f9854e74` `4e8d9495` | 9 defectos del uso real corregidos (rutas externas, historia del HEAD, drift con notas desactualizadas, README/CI/Docker detectados) |
| Skills | `83de9a13` `e36f5d01` `bd709ac2` | 9 skills; vault-backup y onboard/sanación corregidas; nuevas vault-sesion, vault-recordar, vault-decision; test que valida cada `vault run` contra el argparse de su tool |

## Revisión independiente (RDD, gentle-ai 4.4.0)

Decisión del propietario: revisar solo los commits de riesgo real. **11 revisiones nativas aprobadas
con recibo** (`review-acknowledged/v1`): `76657573`, `9964d598`, `4410f84d`, `b32dd73f`, `2629f2f8`,
`94f57657`, `ef4a0a46`, `e259f661`, `4a6cf371`, `d0a7c84e`, `78175bd3`. Cada cambio de riesgo además
pasó un verificador independiente. Hallazgo sobre RDD: la señal `process_boundary` mira el fichero y no
el cambio, y en este repo marca alto el 86 % de los commits; el diseño es correcto, la calibración no.

## Pendiente, con su plan

| # | Pendiente | Estado y plan |
|---|---|---|
| 1 | Latencia por llamada | Medida sobre la wheel: `vault run` 1,3-1,5 s (el README promete ~0,3 s). Tres intérpretes por llamada; `vault --version` cuesta 442 ms por `importlib.metadata` y `yaml` en el arranque. Plan: banco reproducible, diferir imports en los tres procesos; lanzar el worker sin el proceso intermedio ahorra ~0,5 s pero toca el aislamiento y requiere decisión y verificador. |
| 2 | 53 advertencias no bloqueantes de RDD | Registradas en el vault de desarrollo. Las de más valor: política vacía o con BOM bloquea escrituras; guardar un requisito queda bloqueado con historia vieja e índice ausente; `vault_write` deja escapar una excepción cruda (AP-51); el escáner de seguridad calcula mal la ruta relativa de un solo fichero. |
| 3 | Documentación menor (D10-D27) y guardianes | CLI/MCP v1.0 en la visión de producto, fila de versión de los commits posteriores a v41.27, roadmaps, PLAN del MCP, anclas rotas, índice de docs. Guardianes ciegos: el contador de cifras aprueba coincidencias, el chequeo de comandos no cubre `vault run`, la propiedad de docs no cubre la raíz. |
| 4 | Big-O restante | El paquete de contexto lee todas las notas para los desacuerdos declarados. |
| 5 | Mejoras menores | Umbral inestable de `vault_kernel`; dos copias de la inserción del lead (`conocimiento._render`, `vault_onboard._escalonar`). |
| 6 | Linux 3.9 y 3.12, dictamen QA con SHA | No corridos en esta ronda final. |
| 7 | Simulación TiendaPOS | El producto usado como tercero de punta a punta; al final. |
| 8 | Abiertos externos | OPEN-07 (contraste con un vault ajeno real), ISO organizacionales, contenido del propietario. |

## Reglas del propietario vigentes (para quien retome)

- Push solo a ramas temporales de trabajo (`05_tmp/...`), **nunca a `main`**; sin forzar. Merge, CI,
  tag y publicación los decide el propietario, de a una decisión.
- Revisión RDD nativa solo para commits que tocan un riesgo real (seguridad o guardas, datos
  persistidos, contratos que otros consumen, concurrencia, instaladores/release); al resto, el
  `gentle-ai review assess` por commit y su resultado anotado.
- Commits a nombre del propietario («Carlos Ivan CM»), Conventional Commits, sin atribución a la IA.
- Nada se inventa en las notas: lo que no se sabe va como `> _Pendiente: ..._`; nada se borra
  (no-derogación); lo derivado se regenera con su dueño.
- Engram es una herramienta externa, no parte del producto. macOS queda fuera (falla cerrado).
- Las notas de trabajo van al vault de desarrollo (`vault dev codex`, repo `devcicm/vault-dev-codex`):
  notas nuevas y sucesoras; solo el seguimiento y los registros de defectos se actualizan en el lugar.

## Cómo retomar en otra máquina u otro agente

1. `git clone` del repo y `git checkout 05_tmp/workspace_miniserver`; `python -m pip install -e .[dev]`.
   Si hay un install editable de otro checkout, correr con `PYTHONPATH="<repo>;<repo>/scripts"`
   (en Windows, rutas con `cygpath -w`).
2. Antes de cada commit: los tests que alcanzan al cambio (`python scripts/vault_test_scope.py
   --changed --correr`), las puertas rápidas (`python scripts/vault_gate.py --strict --nivel rapida`)
   y además las guardas transversales que esta ronda dejó pasar dos veces:
   `tests/test_filtro_de_expresiones_regulares.py`, `tests/test_piso_python.py` y
   `python scripts/vault_tests_higiene.py --check --strict`. Tras cambiar el registro de entorno,
   `python scripts/vault_arch.py --sync-env`; tras el catálogo, `vault_mcp_catalog.py --sync`.
3. La suite completa nunca en paralelo con otra corrida pesada (agota memoria en esta máquina y el
   fallo parece del código: `0xC0000142`). Un solo `pytest -n 2` por vez.
4. RDD: `gentle-ai review assess --base-ref <padre> --committed-only` por commit, en un clon sin
   ficheros sin rastrear; para revisar un commit histórico, el clon debe estar en ese commit.
5. El estado detallado, los hallazgos y el seguimiento vivo están en el vault de desarrollo:
   `01_Projects/vault-obsidian-architecture-seguimiento-de-pendientes.md` (secciones A-L),
   `19_Audits/cierre-ronda-workspace-miniserver-2026-11-23.md` y los registros de `18_Bugs/`. Los
   logbooks completos de la ronda (specs con los pedidos textuales y cada decisión) están archivados
   tal cual en `10_Migrated/fuentes/logbooks-workspace-miniserver/` de ese vault.

## Decisiones del propietario pendientes

Merge a `main` y sincronizar el MCP de producción; CI, release y tag v41.27; lanzar el worker sin el
proceso intermedio; el script de instalación de `@github/keytar`; las copias de skills en `~/.codex`.
