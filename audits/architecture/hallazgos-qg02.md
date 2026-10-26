# Hallazgos de QG-02 — dos escenarios medidos

**Generado por:** `audits/architecture/generar_informe.py`
**SHA:** `ab31bf3b095effb81625464d19f2cf80ab72e35c`

## Escenario A — sandbox canónico (el vault de evidencia del repo)

- Total: **14** · controles ejecutados: `True` · por norma: `{'CN-03': 5, 'AP-07': 4, 'AP-64': 4, 'AP-36': 1}`

## Escenario B — runtime limpio de certificación (creado por el producto)

- Total: **0** · controles ejecutados: `True` · por norma: `{}`

**Comparación:** el sandbox canónico acumula 14 hallazgos que son
**reales** (no fixtures adversariales): 12 en cuatro ADR de la evidencia
de MCP, 1 en una nota de conocimiento y 1 de contención (AP-36) que
procede de una ejecución previa. El runtime limpio creado por el
propio producto deja **1** hallazgo (AP-39 en la bitácora de
vocabulario): ese es un defecto **del producto**, no del entorno.

| ID | Norma | Ruta | Observado | Entorno | Clasificación | Severidad |
|---|---|---|---|---|---|---|
| INC-0001 | CN-03 | `03_Decisions/adr-001-mcp-transport.md` | status 'accepted' fuera del vocabulario canónico ['approved', 'archived', 'deprecated', 'd | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0002 | AP-07 | `03_Decisions/adr-001-mcp-transport.md` | ADR incompleto — secciones faltantes: Contexto, Decisión, Consecuencias. | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0003 | AP-64 | `03_Decisions/adr-001-mcp-transport.md` | Decisión cerrada sin `responsable`: nadie responde de su porqué. | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0004 | CN-03 | `03_Decisions/mcp-transport-contract.md` | status 'accepted' fuera del vocabulario canónico ['approved', 'archived', 'deprecated', 'd | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0005 | AP-07 | `03_Decisions/mcp-transport-contract.md` | ADR incompleto — secciones faltantes: Contexto, Decisión, Consecuencias. | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0006 | AP-64 | `03_Decisions/mcp-transport-contract.md` | Decisión cerrada sin `responsable`: nadie responde de su porqué. | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0007 | CN-03 | `03_Decisions/mcp-transport-operations.md` | status 'accepted' fuera del vocabulario canónico ['approved', 'archived', 'deprecated', 'd | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0008 | AP-07 | `03_Decisions/mcp-transport-operations.md` | ADR incompleto — secciones faltantes: Contexto, Decisión, Consecuencias. | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0009 | AP-64 | `03_Decisions/mcp-transport-operations.md` | Decisión cerrada sin `responsable`: nadie responde de su porqué. | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0010 | CN-03 | `03_Decisions/mcp-transport-provenance.md` | status 'accepted' fuera del vocabulario canónico ['approved', 'archived', 'deprecated', 'd | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0011 | AP-07 | `03_Decisions/mcp-transport-provenance.md` | ADR incompleto — secciones faltantes: Contexto, Decisión, Consecuencias. | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0012 | AP-64 | `03_Decisions/mcp-transport-provenance.md` | Decisión cerrada sin `responsable`: nadie responde de su porqué. | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0013 | CN-03 | `07_Knowledge/parser-evidence.md` | status 'active' fuera del vocabulario canónico ['approved', 'archived', 'deprecated', 'dra | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0014 | AP-36 | `../../vault-backups` | 'vault-backups' existe 2 nivel(es) por encima del vault (<RUTA-LOCAL> Ivan\Documents\GitHu | escenario A (sandbox canonico) | contaminacion de ejecuciones previas | critical |
| INC-0015 | AP-39 | `19_Audits/vocabulary/tag-ledger.json` | 3 terminos en uso sin memoria canonica (command, hub, nav) en un runtime recien creado por | escenario B (runtime limpio creado por el producto) | violacion real del producto (CORREGIDA) | medium |

## Fichas completas

### INC-0001 — CN-03 (`03_Decisions/adr-001-mcp-transport.md`)

- **Observado:** status 'accepted' fuera del vocabulario canónico ['approved', 'archived', 'deprecated', 'draft', 'implemented', 'in-progress', 'obsolete', 'planned', 'reviewed', 'stub', 'template', 'verified'].
- **Entorno:** escenario A (sandbox canonico)
- **Causa raíz:** status fuera del vocabulario canonico en un documento de decision del propio vault de evidencia
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión?:** no
- **Quality Gate:** QG-02

### INC-0002 — AP-07 (`03_Decisions/adr-001-mcp-transport.md`)

- **Observado:** ADR incompleto — secciones faltantes: Contexto, Decisión, Consecuencias.
- **Entorno:** escenario A (sandbox canonico)
- **Causa raíz:** ADR sin las secciones obligatorias (Contexto, Decision, Consecuencias)
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión?:** no
- **Quality Gate:** QG-02

### INC-0003 — AP-64 (`03_Decisions/adr-001-mcp-transport.md`)

- **Observado:** Decisión cerrada sin `responsable`: nadie responde de su porqué.
- **Entorno:** escenario A (sandbox canonico)
- **Causa raíz:** decision cerrada sin `responsable`: nadie responde de su porque
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión?:** no
- **Quality Gate:** QG-02

### INC-0004 — CN-03 (`03_Decisions/mcp-transport-contract.md`)

- **Observado:** status 'accepted' fuera del vocabulario canónico ['approved', 'archived', 'deprecated', 'draft', 'implemented', 'in-progress', 'obsolete', 'planned', 'reviewed', 'stub', 'template', 'verified'].
- **Entorno:** escenario A (sandbox canonico)
- **Causa raíz:** status fuera del vocabulario canonico en un documento de decision del propio vault de evidencia
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión?:** no
- **Quality Gate:** QG-02

### INC-0005 — AP-07 (`03_Decisions/mcp-transport-contract.md`)

- **Observado:** ADR incompleto — secciones faltantes: Contexto, Decisión, Consecuencias.
- **Entorno:** escenario A (sandbox canonico)
- **Causa raíz:** ADR sin las secciones obligatorias (Contexto, Decision, Consecuencias)
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión?:** no
- **Quality Gate:** QG-02

### INC-0006 — AP-64 (`03_Decisions/mcp-transport-contract.md`)

- **Observado:** Decisión cerrada sin `responsable`: nadie responde de su porqué.
- **Entorno:** escenario A (sandbox canonico)
- **Causa raíz:** decision cerrada sin `responsable`: nadie responde de su porque
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión?:** no
- **Quality Gate:** QG-02

### INC-0007 — CN-03 (`03_Decisions/mcp-transport-operations.md`)

- **Observado:** status 'accepted' fuera del vocabulario canónico ['approved', 'archived', 'deprecated', 'draft', 'implemented', 'in-progress', 'obsolete', 'planned', 'reviewed', 'stub', 'template', 'verified'].
- **Entorno:** escenario A (sandbox canonico)
- **Causa raíz:** status fuera del vocabulario canonico en un documento de decision del propio vault de evidencia
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión?:** no
- **Quality Gate:** QG-02

### INC-0008 — AP-07 (`03_Decisions/mcp-transport-operations.md`)

- **Observado:** ADR incompleto — secciones faltantes: Contexto, Decisión, Consecuencias.
- **Entorno:** escenario A (sandbox canonico)
- **Causa raíz:** ADR sin las secciones obligatorias (Contexto, Decision, Consecuencias)
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión?:** no
- **Quality Gate:** QG-02

### INC-0009 — AP-64 (`03_Decisions/mcp-transport-operations.md`)

- **Observado:** Decisión cerrada sin `responsable`: nadie responde de su porqué.
- **Entorno:** escenario A (sandbox canonico)
- **Causa raíz:** decision cerrada sin `responsable`: nadie responde de su porque
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión?:** no
- **Quality Gate:** QG-02

### INC-0010 — CN-03 (`03_Decisions/mcp-transport-provenance.md`)

- **Observado:** status 'accepted' fuera del vocabulario canónico ['approved', 'archived', 'deprecated', 'draft', 'implemented', 'in-progress', 'obsolete', 'planned', 'reviewed', 'stub', 'template', 'verified'].
- **Entorno:** escenario A (sandbox canonico)
- **Causa raíz:** status fuera del vocabulario canonico en un documento de decision del propio vault de evidencia
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión?:** no
- **Quality Gate:** QG-02

### INC-0011 — AP-07 (`03_Decisions/mcp-transport-provenance.md`)

- **Observado:** ADR incompleto — secciones faltantes: Contexto, Decisión, Consecuencias.
- **Entorno:** escenario A (sandbox canonico)
- **Causa raíz:** ADR sin las secciones obligatorias (Contexto, Decision, Consecuencias)
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión?:** no
- **Quality Gate:** QG-02

### INC-0012 — AP-64 (`03_Decisions/mcp-transport-provenance.md`)

- **Observado:** Decisión cerrada sin `responsable`: nadie responde de su porqué.
- **Entorno:** escenario A (sandbox canonico)
- **Causa raíz:** decision cerrada sin `responsable`: nadie responde de su porque
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión?:** no
- **Quality Gate:** QG-02

### INC-0013 — CN-03 (`07_Knowledge/parser-evidence.md`)

- **Observado:** status 'active' fuera del vocabulario canónico ['approved', 'archived', 'deprecated', 'draft', 'implemented', 'in-progress', 'obsolete', 'planned', 'reviewed', 'stub', 'template', 'verified'].
- **Entorno:** escenario A (sandbox canonico)
- **Causa raíz:** status fuera del vocabulario canonico en un documento de decision del propio vault de evidencia
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión?:** no
- **Quality Gate:** QG-02

### INC-0014 — AP-36 (`../../vault-backups`)

- **Observado:** 'vault-backups' existe 2 nivel(es) por encima del vault (<RUTA-LOCAL> Ivan\Documents\GitHub\vault-backups) — side-effect escrito fuera del vault root.
- **Entorno:** escenario A (sandbox canonico)
- **Causa raíz:** efecto lateral escrito FUERA del vault root (AP-36): un directorio vault-backups existe dos niveles por encima del vault; procede de una ejecucion previa de backup
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** contaminacion de ejecuciones previas
- **Severidad:** critical
- **Acción recomendada:** localizar y purgar el directorio con el dueno de los datos (no se borra desde aqui) y evitar que las ejecuciones escriban fuera del vault
- **¿Requiere decisión?:** sí
- **Quality Gate:** QG-02

### INC-0015 — AP-39 (`19_Audits/vocabulary/tag-ledger.json`)

- **Observado:** 3 terminos en uso sin memoria canonica (command, hub, nav) en un runtime recien creado por el producto
- **Entorno:** escenario B (runtime limpio creado por el producto)
- **Causa raíz:** vault_init crea notas bootstrap con tags que no declaraba como canonicos en su propio tag-registry.json
- **Reproducción:** `python scripts/vault_init.py  # con VAULT_ROOT apuntando a un runtime nuevo; despues python scripts/vault_norms.py --audit --root <rt>`
- **Clasificación:** violacion real del producto (CORREGIDA)
- **Severidad:** medium
- **Acción recomendada:** aplicada: categoria 'bootstrap' en canonical_tags del tag-registry
- **¿Requiere decisión?:** no
- **Quality Gate:** QG-02

## Recomendación de contrato para QG-02 (no se cambia aquí)

1. **Certificar sobre runtime limpio** (escenario B), no sobre el vault
   de evidencia: los hallazgos del sandbox son de contenido y deben
   corregirse como deuda de evidencia, no congelar la puerta.
2. **Corregir el defecto del producto** de AP-39: un runtime recién
   creado no debe violar la norma que el producto certifica (INV-10).
3. **Exigir `completo: true` y cero violaciones en el runtime de
   certificación**, y dejar la higiene del sandbox como verificación
   aparte (no es una puerta de producto).
4. **La contención (AP-36)** se corrige por el dueño de los datos: el
   directorio `vault-backups` fuera del vault no se borra desde aquí.

