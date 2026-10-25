# TD-0008 — Protección de `vault_init --clean` (R04: diseño, sin implementar)

| Campo | Valor |
|---|---|
| Tarea | R04 |
| TD | TD-0008 (P1, vigente) |
| Rama | `fase2/deuda-y-product-readiness-20261025` |
| Estado | **DISEÑO**. No se ha modificado `scripts/vault_init.py` |
| Alcance | `scripts/vault_init.py:216-227` (Step 0 de `--clean`) |

---

## 1. Defecto actual (verificado en el código, no supuesto)

```python
# Step 0: --clean wipes existing content (only if explicitly asked)
if clean and _raiz().exists():
    wiped = []
    for entry in _raiz().iterdir():
        if entry.name == ".locks":
            continue
        if entry.is_dir():
            shutil.rmtree(entry)      # <- borrado recursivo, sin copia
        else:
            entry.unlink()
        wiped.append(entry.name)
    result["steps"].append({"step": "clean", "wiped": wiped})
```

Cuatro propiedades del código actual, cada una con su consecuencia:

1. **Irreversible.** No hay copia, snapshot ni cuarentena previa. Un `--clean`
   sobre el vault equivocado no se deshace.
2. **No verifica el destino.** Borra lo que haya en `VAULT_ROOT` sin comprobar
   que parezca un vault (p. ej. `00_System/`, `17_Preferences/`): un
   `VAULT_ROOT` mal exportado apunta a un directorio de trabajo cualquiera y
   se borra igual.
3. **No pide confirmación ni nombre.** `--clean` es un flag booleano: no hay
   gesto adicional que distinga "quería limpiar" de "lo escribí por error".
4. **Falla a medias.** Borra elemento a elemento mientras itera: si el cuarto
   elemento está bloqueado (fichero abierto en Windows), los tres primeros ya
   no existen y el vault queda en un estado mixto sin registro de qué se
   perdió. `wiped` no llega a emitirse porque la excepción sale antes.

Lo que **no** es un defecto: `.locks` se preserva (deliberado) y `--clean`
exige el flag explícito (no es un efecto colateral de otra ruta).

---

## 2. Alternativas evaluadas

| # | Alternativa | Integridad ante fallo | Coste | Borrado real |
|---|---|---|---|---|
| A | Copia completa a `BACKUP/` y después borrar | Alta | Espacio = vault × 1; tiempo de copia | Sí, tras copia |
| B | Snapshot git (`git stash`/commit temporal) | Alta si el vault es repo | No cubre ficheros ignorados ni no versionados | Depende del repo |
| C | **Rename atómico a cuarentena y purga diferida** | **Alta** (rename es atómico en el mismo volumen) | Casi nulo; espacio durante la ventana | Sí, tras VERIFY |
| D | Rechazar y exigir limpieza manual | Total | Nulo | No |

**B se descarta** como mecanismo principal: el vault puede no ser un repositorio,
y los ficheros ignorados (`.history/`, `00_System/` con datos de runtime) son
justo los que un usuario querría recuperar.

**D se descarta** como única salida: convierte una operación legítima en manual y
no protege a quien la hace a mano.

**Decisión: C como mecanismo principal, A como respaldo.** El rename es atómico
en el mismo volumen y el estado de fallo es siempre "o todo dentro, o todo
fuera". Si el rename falla por cruzar volúmenes (`EXDEV`), se degrada a A
(copia + verificación + borrado) y se declara en el envelope.

---

## 3. Máquina de estados propuesta

```
PRECHECK ──> BACKUP ──> VERIFY_BACKUP ──> READY ──> CLEAN ──> REINITIALIZE ──> VERIFY_RESULT ──> COMPLETED
   │            │              │            │          │             │                │
   │            │              │            │          │             │                └─> FAILED
   │            │              │            │          │             └─> ROLLBACK ──> FAILED
   │            │              │            │          └─> ROLLBACK ──> FAILED
   │            │              │            └─> ROLLBACK ──> FAILED
   │            │              └─> ROLLBACK ──> FAILED
   │            └─> ABORTED (no se toca nada)
   └─> ABORTED (no se toca nada)
```

Cada transición deja un registro en el envelope (`steps[]`) con `estado`,
`motivo` y la ruta de cuarentena si existe. Regla fail-closed: **ningún estado
avanza sin que el anterior haya acreditado su postcondición**.

| Estado | Postcondición exigida antes de avanzar |
|---|---|
| PRECHECK | `VAULT_ROOT` resuelto por `vault_io.get_vault_root()`; contiene marcas de vault (`00_System/` o `17_Preferences/`); el nombre declarado coincide con el del vault |
| BACKUP | Existe la cuarentena `.<nombre>.cuarentena-<TS>/` en el mismo volumen, o la copia `BACKUP/` con el árbol completo |
| VERIFY_BACKUP | El inventario de la copia (rutas + tamaño + sha256) cubre **todos** los elementos de origen; un fichero ilegible ⇒ ROLLBACK |
| READY | `--confirm <nombre>` coincide; `.locks` preservado; plan de borrado calculado (lista cerrada, no `iterdir` en vivo) |
| CLEAN | Cada elemento del plan está dentro de la cuarentena o borrado; ninguno a medias |
| REINITIALIZE | `standard_folders()` creadas; `.gitkeep` presentes |
| VERIFY_RESULT | `vault_audit`/`vault_quality_check` sobre el vault nuevo; inventario del resultado emitido |
| COMPLETED | Envelope con `ok: true` **y** `cuarentena` (ruta) **y** `purga` (`diferida` \| `ejecutada`) **y** `verificacion` |

**Purga diferida:** la cuarentena **no** se borra dentro de `--clean`. Se
conserva hasta un `--purge-backup <TS>` explícito o una retención declarada
(p. ej. 7 días). Borrarla en el mismo acto reintroduce el defecto un paso más
allá: el usuario ya no puede recuperar el error.

---

## 4. Contrato de la CLI (propuesto, NO implementado)

```
python scripts/vault_init.py --clean --confirm <nombre-del-vault>
```

- `--clean` sin `--confirm` ⇒ `INVALID_INPUT` con el comando exacto a ejecutar.
- `--confirm` con nombre distinto al del vault ⇒ `INVALID_INPUT` (no hay
  "confirmar cualquier cosa").
- `--clean --dry-run` ⇒ recorre la máquina hasta READY y emite el plan de
  borrado sin ejecutar CLEAN.
- Exit codes: `0` COMPLETED; `2` ABORTED en PRECHECK; `3` ROLLBACK ejecutado con
  la cuarentena intacta; `4` purga fallida con la cuarentena intacta.
- El envelope conserva el contrato actual (`ok`, `steps`, `vault_root`) y añade
  `cuarentena`, `purga`, `verificacion` — campos **nuevos**, ningún campo
  existente desaparece (`superseded_fields` no aplica).

**Cambio de contrato declarado:** hoy `--clean` no exige `--confirm`. La
propuesta lo exige. Es un endurecimiento deliberado y debe anunciarse en el
changelog de la versión que lo implemente; no se ejecuta en esta tarea.

---

## 5. Plan de rollback

| Punto de fallo | Acción | Estado resultante |
|---|---|---|
| PRECHECK | Nada que deshacer | ABORTED, vault intacto |
| BACKUP (rename falla, copia falla) | Borrar la cuarentena parcial si existe | ABORTED, vault intacto |
| VERIFY_BACKUP (inventario no cubre origen) | Renombrar la cuarentena de vuelta | ABORTED, vault intacto |
| CLEAN (fallo a mitad del plan) | Restaurar desde cuarentena los elementos del plan que ya no están; verificar inventario | ROLLBACK, vault íntegro |
| REINITIALIZE (fallo creando carpetas) | Restaurar desde cuarentena sobre lo creado | ROLLBACK, vault íntegro |
| VERIFY_RESULT (vault nuevo no sano) | Restaurar desde cuarentena; el vault nuevo se descarta | ROLLBACK, vault íntegro |
| Purga | Nunca automática | sin efecto |

El rollback se prueba **provocando cada fallo**, no leyendo el código.

---

## 6. Pruebas propuestas (11)

1. `--clean` sin `--confirm` → `INVALID_INPUT`, vault intacto.
2. `--confirm` con nombre distinto → `INVALID_INPUT`, vault intacto.
3. `VAULT_ROOT` sin marcas de vault → ABORTED en PRECHECK, nada borrado.
4. `--dry-run` → plan de borrado emitido, nada borrado, exit 0.
5. Éxito completo → cuarentena existe, contiene los elementos borrados, exit 0.
6. Fallo a mitad de CLEAN (fichero bloqueado simulado) → ROLLBACK, inventario
   de la cuarentena == inventario del vault previo.
7. Fallo en REINITIALIZE → ROLLBACK, vault íntegro.
8. `VERIFY_BACKUP` con un fichero ilegible → ROLLBACK antes de borrar nada.
9. Rename que cruza volúmenes (EXDEV simulado) → degrada a copia + verificación
   y declara `mecanismo: copia` en el envelope.
10. `.locks` sobrevive en todos los caminos de éxito.
11. La purga diferida no borra la cuarentena sin `--purge-backup`.

Las pruebas 6, 7 y 8 se ejecutan sobre un sandbox temporal **fuera** del runtime
versionado, y ninguna usa datos reales del usuario.

---

## 7. Fuera de alcance de R04

- Implementar la máquina de estados (requiere aprobación del diseño).
- Cambiar `--clean` (el comportamiento público sigue siendo el actual).
- Tocar `scripts/vault_init.py`, sus tests existentes o el catálogo MCP.

## 8. Riesgo residual si se implementa tal cual

- La ventana en que el vault existe dos veces (cuarentena + nuevo) consume
  espacio: se declara en el envelope y se acota con retención.
- Si la cuarentena está en el mismo volumen que el vault, un fallo de disco
  afecta a ambos: el mecanismo protege del error humano, no de la pérdida del
  dispositivo. Se dice en la documentación en lugar de prometerlo.
