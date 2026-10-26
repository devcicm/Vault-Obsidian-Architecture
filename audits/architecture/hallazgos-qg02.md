# Los quince hallazgos de QG-02 — fichas con los dos escenarios

**SHA:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`

- **Escenario A** — sandbox canónico (`vault-sandbox`): 14 hallazgos
- **Escenario B** — runtime limpio creado por el producto: 1 hallazgo

Conclusión: los 14 del sandbox son hallazgos **reales de contenido de
evidencia** (no fixtures adversariales): 12 en cuatro ADR de MCP, 1 en
una nota de conocimiento y 1 de contención (AP-36) procedente de una
ejecución previa. El runtime limpio del producto deja **1** hallazgo
(AP-39): eso es un defecto **del producto** — un runtime recién creado
viola la norma que el producto certifica (invariante INV-10).

| ID | Norma | Ruta | Entorno | Clasificación | Severidad |
|---|---|---|---|---|---|
| INC-0001 | CN-03 | `03_Decisions/adr-001-mcp-transport.md` | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0002 | AP-07 | `03_Decisions/adr-001-mcp-transport.md` | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0003 | AP-64 | `03_Decisions/adr-001-mcp-transport.md` | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0004 | CN-03 | `03_Decisions/mcp-transport-contract.md` | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0005 | AP-07 | `03_Decisions/mcp-transport-contract.md` | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0006 | AP-64 | `03_Decisions/mcp-transport-contract.md` | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0007 | CN-03 | `03_Decisions/mcp-transport-operations.md` | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0008 | AP-07 | `03_Decisions/mcp-transport-operations.md` | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0009 | AP-64 | `03_Decisions/mcp-transport-operations.md` | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0010 | CN-03 | `03_Decisions/mcp-transport-provenance.md` | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0011 | AP-07 | `03_Decisions/mcp-transport-provenance.md` | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0012 | AP-64 | `03_Decisions/mcp-transport-provenance.md` | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0013 | CN-03 | `07_Knowledge/parser-evidence.md` | escenario A (sandbox canonico) | violacion real del producto (contenido de evidencia) | medium |
| INC-0014 | AP-36 | `../../vault-backups` | escenario A (sandbox canonico) | contaminacion de ejecuciones previas | critical |
| INC-0015 | AP-39 | `19_Audits/vocabulary/tag-ledger.json` | escenario B (runtime limpio creado por el producto) | violacion real del producto (el init deja el runtime con una violacion) | medium |

## INC-0001 — CN-03 (`03_Decisions/adr-001-mcp-transport.md`)

- **Entorno:** escenario A (sandbox canonico)
- **Observado:** status 'accepted' fuera del vocabulario canónico ['approved', 'archived', 'deprecated', 'draft', 'implemented', 'in-progress', 'obsolete', 'planned', 'reviewed', 'stub', 'template', 'verified'].
- **Causa raíz:** status fuera del vocabulario canonico en un documento de decision del propio vault de evidencia
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión del propietario?** no

## INC-0002 — AP-07 (`03_Decisions/adr-001-mcp-transport.md`)

- **Entorno:** escenario A (sandbox canonico)
- **Observado:** ADR incompleto — secciones faltantes: Contexto, Decisión, Consecuencias.
- **Causa raíz:** ADR sin las secciones obligatorias (Contexto, Decision, Consecuencias)
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión del propietario?** no

## INC-0003 — AP-64 (`03_Decisions/adr-001-mcp-transport.md`)

- **Entorno:** escenario A (sandbox canonico)
- **Observado:** Decisión cerrada sin `responsable`: nadie responde de su porqué.
- **Causa raíz:** decision cerrada sin `responsable`: nadie responde de su porque
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión del propietario?** no

## INC-0004 — CN-03 (`03_Decisions/mcp-transport-contract.md`)

- **Entorno:** escenario A (sandbox canonico)
- **Observado:** status 'accepted' fuera del vocabulario canónico ['approved', 'archived', 'deprecated', 'draft', 'implemented', 'in-progress', 'obsolete', 'planned', 'reviewed', 'stub', 'template', 'verified'].
- **Causa raíz:** status fuera del vocabulario canonico en un documento de decision del propio vault de evidencia
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión del propietario?** no

## INC-0005 — AP-07 (`03_Decisions/mcp-transport-contract.md`)

- **Entorno:** escenario A (sandbox canonico)
- **Observado:** ADR incompleto — secciones faltantes: Contexto, Decisión, Consecuencias.
- **Causa raíz:** ADR sin las secciones obligatorias (Contexto, Decision, Consecuencias)
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión del propietario?** no

## INC-0006 — AP-64 (`03_Decisions/mcp-transport-contract.md`)

- **Entorno:** escenario A (sandbox canonico)
- **Observado:** Decisión cerrada sin `responsable`: nadie responde de su porqué.
- **Causa raíz:** decision cerrada sin `responsable`: nadie responde de su porque
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión del propietario?** no

## INC-0007 — CN-03 (`03_Decisions/mcp-transport-operations.md`)

- **Entorno:** escenario A (sandbox canonico)
- **Observado:** status 'accepted' fuera del vocabulario canónico ['approved', 'archived', 'deprecated', 'draft', 'implemented', 'in-progress', 'obsolete', 'planned', 'reviewed', 'stub', 'template', 'verified'].
- **Causa raíz:** status fuera del vocabulario canonico en un documento de decision del propio vault de evidencia
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión del propietario?** no

## INC-0008 — AP-07 (`03_Decisions/mcp-transport-operations.md`)

- **Entorno:** escenario A (sandbox canonico)
- **Observado:** ADR incompleto — secciones faltantes: Contexto, Decisión, Consecuencias.
- **Causa raíz:** ADR sin las secciones obligatorias (Contexto, Decision, Consecuencias)
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión del propietario?** no

## INC-0009 — AP-64 (`03_Decisions/mcp-transport-operations.md`)

- **Entorno:** escenario A (sandbox canonico)
- **Observado:** Decisión cerrada sin `responsable`: nadie responde de su porqué.
- **Causa raíz:** decision cerrada sin `responsable`: nadie responde de su porque
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión del propietario?** no

## INC-0010 — CN-03 (`03_Decisions/mcp-transport-provenance.md`)

- **Entorno:** escenario A (sandbox canonico)
- **Observado:** status 'accepted' fuera del vocabulario canónico ['approved', 'archived', 'deprecated', 'draft', 'implemented', 'in-progress', 'obsolete', 'planned', 'reviewed', 'stub', 'template', 'verified'].
- **Causa raíz:** status fuera del vocabulario canonico en un documento de decision del propio vault de evidencia
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión del propietario?** no

## INC-0011 — AP-07 (`03_Decisions/mcp-transport-provenance.md`)

- **Entorno:** escenario A (sandbox canonico)
- **Observado:** ADR incompleto — secciones faltantes: Contexto, Decisión, Consecuencias.
- **Causa raíz:** ADR sin las secciones obligatorias (Contexto, Decision, Consecuencias)
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión del propietario?** no

## INC-0012 — AP-64 (`03_Decisions/mcp-transport-provenance.md`)

- **Entorno:** escenario A (sandbox canonico)
- **Observado:** Decisión cerrada sin `responsable`: nadie responde de su porqué.
- **Causa raíz:** decision cerrada sin `responsable`: nadie responde de su porque
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión del propietario?** no

## INC-0013 — CN-03 (`07_Knowledge/parser-evidence.md`)

- **Entorno:** escenario A (sandbox canonico)
- **Observado:** status 'active' fuera del vocabulario canónico ['approved', 'archived', 'deprecated', 'draft', 'implemented', 'in-progress', 'obsolete', 'planned', 'reviewed', 'stub', 'template', 'verified'].
- **Causa raíz:** status fuera del vocabulario canonico en un documento de decision del propio vault de evidencia
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (contenido de evidencia)
- **Severidad:** medium
- **Acción recomendada:** corregir el documento de evidencia: status canonico, secciones obligatorias y responsable
- **¿Requiere decisión del propietario?** no

## INC-0014 — AP-36 (`../../vault-backups`)

- **Entorno:** escenario A (sandbox canonico)
- **Observado:** 'vault-backups' existe 2 nivel(es) por encima del vault (<RUTA-USUARIO> Ivan\Documents\GitHub\vault-backups) — side-effect escrito fuera del vault root.
- **Causa raíz:** efecto lateral escrito FUERA del vault root (AP-36): un directorio vault-backups existe dos niveles por encima del vault; procede de una ejecucion previa de backup
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** contaminacion de ejecuciones previas
- **Severidad:** critical
- **Acción recomendada:** localizar y purgar el directorio con el dueno de los datos (no se borra desde aqui) y evitar que las ejecuciones escriban fuera del vault
- **¿Requiere decisión del propietario?** sí

## INC-0015 — AP-39 (`19_Audits/vocabulary/tag-ledger.json`)

- **Entorno:** escenario B (runtime limpio creado por el producto)
- **Observado:** 3 término(s) en uso que no son canónicos ni constan en la bitácora ('command', 'hub', 'nav') — vocabulario introducido sin dejar rastro de quién ni cuándo. Correr vault_tags --backfill-ledger para ano
- **Causa raíz:** el init del producto escribe una entrada de vocabulario sin memoria en la bitacora de tags (AP-39)
- **Reproducción:** `python scripts/vault_norms.py --audit --root <runtime>`
- **Clasificación:** violacion real del producto (el init deja el runtime con una violacion)
- **Severidad:** medium
- **Acción recomendada:** corregir el init o el registro que produce; es un defecto del producto, no del entorno
- **¿Requiere decisión del propietario?** sí

## Recomendación de contrato para QG-02 (pendiente del propietario)

1. Certificar sobre **runtime limpio de certificación** (escenario B),
   no sobre el vault de evidencia.
2. Corregir el defecto del producto AP-39 (INV-10).
3. La higiene del vault de evidencia (los 14) es deuda de contenido,
   no una puerta de producto.
4. La contención AP-36 se resuelve con el dueño de los datos
   (`vault-backups` fuera del vault no se borra desde aquí).

