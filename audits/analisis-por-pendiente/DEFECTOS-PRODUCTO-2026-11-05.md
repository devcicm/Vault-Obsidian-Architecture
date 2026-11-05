# Defectos de producto, candidatos y gaps negativos

Documento **generado**: `python audits/analisis-por-pendiente/generar_defectos_producto.py --vault <vault real>`. Ninguna cifra está escrita a mano (AP-47).

El criterio es el de **quien consume** (regla 7): no «¿está declarado?», sino «¿qué pasa cuando se usa?». Lo que se mide sobre un vault ajeno es **solo lectura**.

## 1. Defectos

| ID | Sev. | Qué |
|---|---|---|
| D-01 | alta | El token del servicio de tokens se commitea: vive en el vault y no está en la lista de ignorados. |
| D-02 | media | Lo borrado y la traza del MCP se quedan en el repositorio: `00_System/.trash/` y `.mcp-trace-log.json` no se ignoran, aunque `.tool-trace.json` sí. |
| D-03 | alta | Un vault anterior a la capa de git se queda con repo y **sin `.gitignore`**: el versionado rastrea todo lo volátil. |
| D-04 | baja | La remediación de `vault_audit` nombra un modelo concreto: «Agregar agent: deepseek». |
| D-05 | media | `docs/product/overview.md` publica cifras que ya no son ciertas, y el guard de cifras no las ve. |
| D-06 | media | En Windows, `os.chmod(0o600)` sobre el token no protege nada: solo toca el bit de solo-lectura. |
| D-07 | baja | Siete `assert` en código de producto desaparecen con `python -O`, incluidos los de `vault_release`. |
| D-08 | baja | El catálogo declara AP-04 con `enforcement: audit` y ninguna tool la mide; el plano la cuenta como descubierta. |

### D-01 — El token del servicio de tokens se commitea: vive en el vault y no está en la lista de ignorados.

- **Evidencia**: `vault/consulta/repositorio.py:93` devuelve `00_System/token-usage/token-service.token`; `vault/kernel/vcs.py:48` no ignora esa carpeta y `commit_de_operacion` hace `git add -A` (`vcs.py:108`).
- **Efecto en el consumidor**: La primera operación que escriba en el vault después de arrancar el servicio deja la credencial en `git log`. En un vault con remoto, se publica.
- **Arreglo**: La política pasa a **solo notas `.md`**: `IGNORADOS_EN_GIT` deja fuera todo lo que no sea markdown y `IGNORADOS_POR_RIESGO` nombra la credencial para que el test la cruce con su dueño. Ver C-01/C-02.

### D-02 — Lo borrado y la traza del MCP se quedan en el repositorio: `00_System/.trash/` y `.mcp-trace-log.json` no se ignoran, aunque `.tool-trace.json` sí.

- **Evidencia**: `vault/kernel/vcs.py:48-53`; `vault_delete --force` mueve a `.trash/` y el commit siguiente lo rastrea. La traza del MCP la escribe `mcp/nodejs/vault-mcp-server.mjs` y cambia en cada llamada.
- **Efecto en el consumidor**: `vault_delete` no borra de verdad —la nota recuperable queda en la historia— y cada commit del vault arrastra un diff de traza que no interesa a nadie.
- **Arreglo**: Re-ignorar `.history/`, `vault-backups/`, `.locks/` y `00_System/.trash/` **después** de `!*.md`: contienen `.md` que no son notas y la negación los devolvería. Ver C-02.

### D-03 — Un vault anterior a la capa de git se queda con repo y **sin `.gitignore`**: el versionado rastrea todo lo volátil.

- **Evidencia**: `scripts/vault_init.py:1058-1073`: el `.gitignore` se escribe dentro de `if not (destino / '.git').exists()`, así que un vault que ya tenía repo nunca lo recibe. El comentario del propio código cita la medida que lo motivó —«99 de 345 ficheros versionados eran versiones de `.history/`»— y ese vault sigue sin el fichero: el arreglo se aplicó a la rama que no vuelve a ejecutarse para el caso medido. Ver «medición del vault».
- **Efecto en el consumidor**: Cada operación versiona `.history/`, `.trash/`, trazas y el token. El repo crece sin techo y el diff de cada commit es ruido.
- **Arreglo**: `commit_de_operacion` garantiza el ignore antes de `add -A` (C-01) y una reparación explícita para vaults existentes (C-03).

### D-04 — La remediación de `vault_audit` nombra un modelo concreto: «Agregar agent: deepseek».

- **Evidencia**: `scripts/vault_audit.py:2952`.
- **Efecto en el consumidor**: El consejo que recibe un consumidor depende de con qué modelo trabajaba el autor de la tool. Es el criterio del productor filtrado en la salida del producto.
- **Arreglo**: Derivar de `VAULT_AGENT` o dejar el campo como `<agente>`; nunca un nombre propio. Ver C-04.

### D-05 — `docs/product/overview.md` publica cifras que ya no son ciertas, y el guard de cifras no las ve.

- **Evidencia**: El documento se declara `Estado: Draft`, `revisión: manual`, fechado el 2026-09-20, y afirma `expone 116 tools`, `Estándar: v40.34` y `Toolkit: 41.0 (próxima release)`. El registro dice otra cosa: ver «afirmaciones contrastadas». El patrón de `vault_doc_counts` exige `expone N de las` (`vault_doc_counts.py:315`), así que `expone 116 tools` no casa.
- **Efecto en el consumidor**: Un documento de producto que un consumidor lee para decidir si instalar miente en tres cifras, y la puerta de AP-47 sale verde.
- **Arreglo**: O se deriva del registro y se añade el patrón que falta, o se archiva como histórico. Ver C-05.

### D-06 — En Windows, `os.chmod(0o600)` sobre el token no protege nada: solo toca el bit de solo-lectura.

- **Evidencia**: `scripts/vault_token_service.py:448`, sin rama por plataforma; en POSIX funciona, en Windows las ACL no cambian y el `except OSError` esconde el no-op.
- **Efecto en el consumidor**: El servicio dice que la credencial «solo la lee quien puede leer el vault» y en Windows cualquier proceso del usuario puede leerla. La protección es declarativa, no efectiva.
- **Arreglo**: `icacls`/ACL explícita en Windows, o `%LOCALAPPDATA%`, o declarar el límite en el docstring. Ver C-06.

### D-07 — Siete `assert` en código de producto desaparecen con `python -O`, incluidos los de `vault_release`.

- **Evidencia**: Ver «huellas estáticas»: `vault_release.py` valida banner, badge y `pyproject` con `assert`.
- **Efecto en el consumidor**: Un release lanzado con `-O` se publica sin validar sus cuatro sitios de versión, en silencio.
- **Arreglo**: Cambiar los `assert` de rutas de producto por `if … raise`.

### D-08 — El catálogo declara AP-04 con `enforcement: audit` y ninguna tool la mide; el plano la cuenta como descubierta.

- **Evidencia**: `NORM_CATALOG` (AP-04: `tools_enforcing=[]`, `tools_detecting=[]`, sin `cobertura_parcial`); `vault_blueprint.py:438` la lista como «sin detector».
- **Efecto en el consumidor**: Dos registros dicen cosas distintas de la misma norma. Quien lea el catálogo cree que hay un audit; no lo hay.
- **Arreglo**: Implementar la señal decidible o declararla `cobertura_descubierta` en el catálogo. Ver C-07.

## 2. La medición del vault (lo que acaba dentro de git)

- Vault: `~/.vault-master/gestion`
- Repo: sí · commits: **4** · ficheros rastreados: **265**
- `.gitignore`: **sí** (107 bytes)

| Ruta volátil | Clase | ¿Ignorada por el dueño? | Rastreados |
|---|---|---|---:|
| `.history/` | versiones por nota | sí | 0 |
| `vault-backups/` | copias de seguridad | sí | 0 |
| `.locks/` | locks de escritura | sí | 0 |
| `00_System/.tool-trace.json` | traza de operaciones | sí | 0 |
| `00_System/.mcp-trace-log.json` | traza del servidor MCP | sí | 0 |
| `00_System/.trash/` | contenido borrado | sí | 0 |
| `00_System/token-usage/` | credencial del servicio de tokens | sí | 0 |

**Total de ficheros volátiles rastreados: 0**.

Lo que el dueño del versionado ignora hoy: `*`, `!*/`, `!*.md`, `!.gitignore`, `.history/`, `vault-backups/`, `.locks/`, `00_System/.trash/`, `00_System/token-usage/`.

Volátiles **sin cubrir** por el dueño: ninguno.

## 3. Afirmaciones de producto contrastadas con su registro

| Afirmación | Dice el documento | Dice el registro | ¿Coincide? |
|---|---:|---:|---|
| tools expuestas por MCP | 116 | 98 | **no** |
| tools JS-native | 9 | 2 | **no** |
| versión del estándar | v40.34 | v41.26 | **no** |
| toolkit publicado como «próxima» | 41.0 | v41.26 | **no** |

El patrón de AP-47 para esa cifra es `expone\s+(\d+)\s+de las`; sobre la frase del documento casa: **no**.

## 4. Gaps negativos (lo que ninguna puerta mide)

### 4.1 El catálogo declara 7 coberturas parciales

Están declaradas: el catálogo no las da por cubiertas, así que son deuda honesta, no un hallazgo. Se listan porque **son** el mapa de lo que ningún guard ve.

- **AP-01** (audit) — Documentación alucinada: Estuvo descubierta hasta v41.3. `vault_drift_detect --mode vigencia` mide **la parte que la nota declara**: un fichero listado en `files:` que no existe en el repo sale en `codigo_inexistente` con la norma nombrada. Desd…
- **AP-02** (audit) — Proliferación de versiones del mismo documento: Estuvo descubierta desde v40.11: las hermanas AP-17 y AP-18 se medían y la variante same-folder no la veía nadie, porque `status-v1.md` y `status-v2.md` no son idénticos por hash ni tienen por qué pasar el umbral de títu…
- **AP-05** (audit) — Múltiples fuentes de verdad para el mismo dato: Detectada desde v40.15 **en su parte decidible**, y el resto se declara en vez de darse por cubierto. `vault_fuente_unica` compara valores **tipados** —IP, URL, puerto, semver— escritos como `clave: valor` dentro de un m…
- **AP-08** (audit) — Documentación anclada a versiones obsoletas: Estuvo descubierta hasta v41.3. `vault_drift_detect --mode vigencia` mide **la mitad que la nota declara**: compara su `updatedAt` con el último commit de los ficheros que lista en `files:`, y cuenta aparte las notas sin…
- **AP-17** (audit) — Canonical-shadow duplication: `vault_audit._detect_canonical_shadow` mide dos formas decidibles: la del título (`SequenceMatcher` ≥ 0.85) y, desde v41.3, la identidad que la nota declara —`aliases:` y `files:`, con el criterio de resolución de Obsidi…
- **AP-51** (guard+audit) — La tool culpa al dato de su propio fallo: Detectada desde v41.10 por si el fallo **llega al llamante**, no por si deja rastro: una llamada suelta solo expone si muta un contenedor o si llama a una función del mismo módulo que lo hace (`vault_blame_audit.exposito…
- **AP-52** (guard+audit) — El error se emite fuera del contrato del catalogo: Detectada en su parte decidible: literales, `var["k"] = …` y `var.update(…)` con un dict literal o una variable asignada una sola vez a uno (`vault_error_contract._literales_unicos`, v41.10). Lo que no se sigue —y no se …

### 4.2 Normas con enforcement medible y sin tool

- **AP-04** (audit, high) — Features aspiracionales documentadas como implementadas: sin `cobertura_parcial` declarada.

### 4.3 Carpetas con `.py` que ningún barrido de código recorre

Los barridos usan `CARPETAS_DE_CODIGO`: `cli`, `mcp`, `scripts`, `tests`, `vault`.

| Carpeta | Ficheros `.py` | ¿Barrida? | Qué es |
|---|---:|---|---|
| `audits/` | 29 | **no** | instrumentos de análisis; declarados en el layout, sin barrido de código |
| `cli/` | 9 | sí | código del toolkit |
| `empaquetado/` | 3 | **no** | hooks de construcción de la wheel; no son producto |
| `normas/` | 337 | **no** | paquetes de norma: sus `guard.py` y `test_*.py` los descubre pytest y los vigila `--check-framework` |
| `scripts/` | 179 | sí | código del toolkit |
| `tests/` | 564 | sí | código del toolkit |
| `vault/` | 148 | sí | código del toolkit |
| `vault_toolkit/` | 99 | **no** | capa de despacho del producto: `loading.py` tiene lógica y no la mide ninguna puerta (C-08) |

### 4.4 `vault_criterios` mide 41 de 170 módulos

Salta los módulos que ni nombran `*.md` ni filtran notas por sufijo: un módulo puede reimplementar el criterio sin repetir la constante y el guard no lo verá. Es una cobertura parcial **medida**, no declarada en el catálogo.

### 4.5 Por qué el defecto del versionado pasó la CI

El test `tests/test_vcs_capa_de_git.py` fija los patrones de la política (`*`, `!*.md`, `!.gitignore`, `.history/`, `vault-backups/`, `00_System/.trash/`, `00_System/token-usage/`) y **sí** comprueba el resultado en el índice (`git ls-files`), que es el criterio del consumidor. El caso «vault que ya tenía repo» **sí** se prueba: la garantía vive en `commit_de_operacion`, que corre en cada escritura.

## 5. Huellas estáticas

| Clase | Sitios |
|---|---:|
| `chmod` con permiso `0600`/`0700` | 1 en 1 ficheros |
| `assert` en código de producto | 7 en 4 ficheros |
| `utcnow()`/`utcfromtimestamp` (deprecados desde 3.12) | 115 en 56 ficheros |
| Remediación con un modelo hardcodeado | 1 en 1 ficheros |

- **chmod**: `scripts/vault_token_service.py`.
- **assert**: `scripts/vault_grafo_import.py`, `scripts/vault_release.py`, `vault/product_cli.py`, `vault/gobernanza/controles.py`.
- **modelo hardcodeado**: `scripts/vault_audit.py`.

## 6. Candidatos

| ID | Qué | Coste | Beneficio |
|---|---|---|---|
| C-01 | `commit_de_operacion` garantiza el ignore antes de `add -A`. | Una función pequeña en el dueño del versionado y un test; repara el vault la primera vez que se opera en él. | Cierra D-01/D-02/D-03 sin pedirle nada a la persona. |
| C-02 | Separar `IGNORADOS_EN_GIT` (ruido) de `IGNORADOS_POR_RIESGO` (credenciales y borrado), y test que cruce las rutas que producen los dueños. | Una constante y un test de contrato. | El día que una tool escriba un secreto nuevo dentro del vault, la puerta lo dice. |
| C-03 | Reparación explícita para vaults existentes (`vault_init --repair` o `vault_undo` companion). | Un verbo más y su docstring; toca `.gitignore` y nada más. | Los vaults ya creados salen del estado de D-03 sin migración manual. |
| C-04 | Quitar el nombre propio de la remediación de AP-16 y derivarlo de `VAULT_AGENT`. | Dos líneas. | El producto deja de recomendar el modelo del autor. |
| C-05 | Cubrir `docs/product/` con `vault_doc_counts` (patrón `expone N tools`) o archivarlo. | Un patrón y, si se archiva, mover un fichero. | Las cifras del documento de producto se regeneran o dejan de publicarse. |
| C-06 | Credencial con ACL real en Windows o fuera del vault. | Depende de la vía; la más barata es `%LOCALAPPDATA%`. | La promesa de SP-04 pasa a ser cierta en las dos plataformas. |
| C-07 | AP-04: implementar la señal o declararla descubierta en el catálogo. | Catálogo + test; implementarla es una heurística de prosa. | Un solo registro sobre lo que se mide, que es lo que AP-55 persigue. |
| C-08 | Barrer `vault_toolkit/` en clones y criterios, ahora que los adaptadores son generados. | Excluir `operations/` (generado, idéntico por construcción) y medir `loading.py` y el `__init__`. | La capa de despacho del producto entra en el barrido sin llenar la baseline. |

## 7. Estado tras el arreglo

Una deuda que se salda no se borra: pasa a `saldada` con la evidencia de que está cerrada. Esto se mide en el dueño, no en la intención.

| Defecto | Estado | Evidencia |
|---|---|---|
| D-01 | saldado | `IGNORADOS_POR_RIESGO` cubre la credencial |
| D-02 | saldado | `.trash/` cubierto y `.mcp-trace-log.json` cubierto |
| Notas | sí | la política deja versionar `*.md` y el propio `.gitignore` |
| D-03 | saldado | `commit_de_operacion` repara el ignore en cada escritura y `vault_init` usa el mismo dueño. Los ficheros ya rastreados se dejan en la traza (`rastreados_ignorados`) y retirarlos del índice es una decisión del dueño, no un efecto colateral. |

El vault medido ya no rastrea volátiles: tiene su `.gitignore` y su índice solo lleva notas. El `HEAD` de vuelta de esa limpieza está en el registro del vault.

## 8. Lo que se midió y está limpio

No todo es hallazgo. Estas cosas se probaron y no dieron defecto:

- **Las 26 puertas rápidas** en verde sobre este mismo árbol.
- **La paridad de contratos**: toda tool del catálogo tiene entrada en `tool-spec.json` y ninguna tiene backend duplicado Python + Node.
- **El error envelope**: ningún envelope nuevo fuera de `ERROR_CATALOG` (AP-52) en su parte decidible.
- **Las escrituras**: AP-36 en verde; sin escrituras fuera del vault.
- **git**: AP-68 sin baseline y sin sitios fuera del dueño.
- **Código muerto**: 0 (barrido de dark data, 2026-11-05).

