# Backlog priorizado — fase 2

**Derivado de:** `audits/fase2/inventario-deuda.yaml` (registro canonico de la fase).
**Estado:** PENDIENTE DE DECISION DEL PROPIETARIO. Ningun trabajo de remediacion esta autorizado todavia:
esta entrega es el diagnostico y el plan (regla de alcance de la orden de fase 2).

## Separacion de la deuda

**BLOQUEANTE para entregar a terceros** (impide un release defendible):

| ID | Sev | Hallazgo | Por que bloquea | Lote |
|---|---|---|---|---|
| TD-0001 | P1 | El job de CI de la wheel no instala el paquete | Sin el, la validacion de producto en CI es imposible: QG-07 no puede apoyarse en ningun veredicto de CI | L3 |
| TD-0003 | P1 | Un control con dependencia fallida informa cero hallazgos | Un audit puede mentir: es la confianza en QG-02 y en todo resultado de gobernanza | L2 (investigacion) |

**DIFERIBLE con mitigacion conocida** (no impide el release, pero su medida):

| ID | Sev | Hallazgo | Nota | Lote |
|---|---|---|---|---|
| TD-0002 | P2 | Trazas runtime dentro del paquete de la wheel | Su severidad real depende de que datos contengan: se mide en L3 y sube si hay datos de sesion | L3 |
| TD-0005 | P2 | Seis documentos de producto sin clasificar | Afecta a la confianza del tercero en la guia; no al comportamiento | L4 |
| TD-0006 | P2 | Las baselines estan por encima de su objetivo declarado (5 vs 4; 37 vs 30), con plazo 2027-03-31 | Es observabilidad: el mecanismo mide que no crecen, no la aproximacion al objetivo | L4 (propuesta) |

**CERRADO:**

| ID | Estado | Resultado |
|---|---|---|
| TD-0004 | corregida | Reconciliacion del snapshot de Archify ejecutable y reproducible: 23/23 pares con ficha identica, 8 accesos clasificados (5 vigentes, 3 resueltos con su commit), 2/2 anclas identicas |

**P0:** ninguno. No hay, con la evidencia reunida, un defecto que justifique P0 (critico de seguridad,
 perdida de informacion o contrato publico comprometido). El recorrido MVP de L3 puede cambiar esto:
si la instalacion limpia revela perdida de datos o corrupcion del runtime, aparece un P0 y se avisa de inmediato.

## Lotes y dependencias

```
L1 arquitectura + reconciliacion      [HECHO]  -> matriz-arquitectonica.md, TD-0004 corregida
   |
   +-> L2 Q04-Q07 (INVESTIGACION)     -> TD-0003: causa, contrato, decision, 3 pruebas propuestas
   |        (implementacion: requiere dictamen posterior)
   |
   +-> L3 producto: wheel + venv + CLI/MCP + paridad
   |        -> TD-0001 (workflow), TD-0002 (artefacto), matriz de paridad, veredicto de readiness
   |
   +-> L4 documental + seguridad + historico
            -> TD-0005, TD-0006, nueva TD de seguridad si aparece
```

Dependencias reales: L3 depende de nada de L2 (son轨道 distintas) y puede empezar ya; L4 no depende de L2;
la correccion de TD-0003 (L2) bloquea el veredicto de QG-02, no el de QG-06.

## Estado de cada QG tras el L1

| QG | Estado | Que falta |
|---|---|---|
| QG-00 identidad y trazabilidad | DISEÑADO (pendiente de formalizar) | Fichero de contrato + reejecucion de los lotes |
| QG-01 arquitectura y contratos | DISEÑADO | Catalogo con los verificadores reutilizados (vault_arch, catalogo, esquemas, pruebas contractuales) |
| QG-02 gobernanza y normas | PARCIAL | El verificador existe (26 puertas); falta el estado de ejecucion de los controles (TD-0003) |
| QG-03 integridad funcional | DISEÑADO | Falta el inventario de idempotencia, recuperacion y preservacion (L3) |
| QG-04 seguridad | DISEÑADO | Falta el inventario de controles con evidencia (L4) |
| QG-05 CLI y MCP | DISEÑADO | Falta la matriz de paridad por operacion (L3) |
| QG-06 instalacion y distribucion | DISEÑADO | Falta la ejecucion real del recorrido (L3) |
| QG-07 aprobacion de producto | DISEÑADO | Depende de QG-01..06 y de CI concluyente (TD-0001) |

## Decisiones que se piden al propietario

1. Autorizar o no la correccion de TD-0001 (workflow de CI) cuando L3 la demuestre: es un cambio de
   una linea de workflow y es la unica via para que CI pueda dictaminar.
2. Autorizar o no la correccion de TD-0003 cuando L2 traiga causa, contrato y pruebas (hoy solo
   investigacion; la implementacion exige dictamen).
3. Fijar la prioridad entre la deuda de entrega (TD-0001, TD-0003) y la preparacion de producto
   (paridad CLI-MCP, instalacion limpia, documentacion).
4. Confirmar que la QA revise cada lote antes de avanzar (regla ya acordada) y que el dictamen de cada
   lote quede en RESPUESTA-QA.md.