# Bitácora de auditoría y transferencia entre agentes — 2026-10-24

> **Estado:** trabajo en curso. Documento de coordinación, no certificación de calidad ni autorización de merge. Actualizar este archivo al concluir cada intervención con evidencia, commit y resultado de pruebas.

## 1. Alcance, aislamiento y reglas de colaboración

- **Repositorio:** `devcicm/Vault-Obsidian-Architecture`.
- **Rama de trabajo:** `audit/archify-governance-20261024`.
- **Objetivo:** auditar arquitectura, puertos, contratos y gobernanza; corregir defectos verificados sin encubrir deuda arquitectónica.
- **Otro agente:** trabaja independientemente sobre problemas de gobernanza; su rama y commits no están verificados aquí.
- **Integración:** no fusionar ni publicar a `main` sin comparación de diffs, pruebas y decisión explícita. Si ambos agentes modifican la misma lógica, reconciliar semánticamente; no elegir cambios por fecha.

## 2. Registro de avances verificables

| Paso | Estado | Evidencia | Validación pendiente |
| --- | --- | --- | --- |
| 1. Rama aislada | Completo | `audit/archify-governance-20261024` | Comparar con el trabajo del otro agente antes de integrar |
| 2. Estabilidad de generación de Gobierno | Cambio aplicado | `scripts/vault_servicio.py` commit `477e412470a6f34e7cd235a49321d3d4e1572326`; `docs/GOBIERNO.md` commit `d7b1b4e38b04b00e361361fc27e6a766b28767c0` | Ejecutar regeneración y check, verificar diff limpio y suite |
| 3. Inspección del paquete Archify | Inspección preliminar | ZIP entregado en conversación: tres diagramas de contextos, cruces y onboarding; HTML, JSON, capturas y reportes | Trazar los datos extraídos a módulos e imports del checkout actual |
| 4. Dependencia Kernel → Autoría | Hallazgo documentado | `audits/2026-10-24-kernel-autoria.md`, commit `4091f49d4270b558221fdfa59850aadf62175df1` | Evaluar interfaz, consumidores, regresión y decisión de refactor |
| 5. Puertos y contratos | Pendiente | Ocho accesos fuera de puerto **declarados en el paquete Archify**, no ocho defectos ya comprobados en código actual | Verificar uno a uno, corregir y probar |
| 6. Validación integral | Pendiente | Ninguna ejecución de suite confirmada | Gates, pruebas de regresión y revisión de artefactos derivados |

## 3. Evidencia de los cambios ya aplicados

### G-01 — Fecha variable en documento derivado

**Antes:** el generador añadía la fecha de ejecución a `docs/GOBIERNO.md`, creando diferencias en regeneraciones realizadas en distintos días.

**Después:** `scripts/vault_servicio.py` emite `_Derivado de los registros canónicos. ` sin `date.today()`. El encabezado derivado en `docs/GOBIERNO.md` fue sincronizado. Ambos archivos se recuperaron nuevamente de la rama y se comprobó el encabezado nuevo.

**Límite:** aún no se ha ejecutado `--check` ni la batería de tests. Esta modificación puede solaparse con la corrección del otro agente.

### A-01 — Kernel → Autoría

- `scripts/vault_arch.py` registra explícitamente `_cruce("kernel", "autoria", "permanente", "kernel", ...)`.
- `scripts/vault_errors.py` importa `from vault.autoria.voz import speak as _speak_estable`.
- `vault/autoria/voz.py` implementa el servicio, con imports diferidos hacia normas, vocabulario y raíz.
- **Interpretación:** cruce autorizado por presupuesto; no puede declararse violación sin estudiar la semántica del puerto. Existe acoplamiento directo con el módulo concreto, que merece revisión.
- **Estado:** solo auditoría documentada; no se cambió el comportamiento.

## 4. Paquete Archify recibido

Archivo de entrada: `mapa-contextos.visual-check.2048x1320.light.zip` (adjunto a la conversación; **no** incorporado al repositorio).

Contenido inspeccionado: `mapa-contextos.html`, `mapa-cruces.html`, `mapa-onboarding.html`, `candidata-contextos.json`, `candidata-cruces.json`, `candidata-onboarding.json`, capturas claro/oscuro y reportes de comprobación.

Datos **reportados por Archify**: 37 cruces y 8 accesos fuera de puerto. Son métricas del paquete, no un recálculo sobre la rama actual. Los focos identificados en la revisión preliminar son:

| Dirección | Cantidad reportada | Área |
| --- | ---: | --- |
| Autoría → Índices | 2 | Etiquetas |
| Ciclo de vida → Índices | 1 | Indexación |
| Gobernanza → Meta-toolkit | 4 | Cobertura, catálogo y smoke |
| Gobernanza → Autoría | 1 | Voz |
| **Total** | **8** | Requiere rastreo por símbolo |

Funciones citadas en el análisis preliminar: `check_params`, `notas_indexables`, `apply_vocabulary`, `record_new_tags`. La atribución exacta de cada función a cada cruce debe contrastarse con el JSON y con el código; **no se presenta como comprobada**.

**Precaución temporal:** contextos y cruces citan la revisión `f5f6921`, onboarding `6e460b8`. No asumir que representan el mismo estado de código.

## 5. Trabajo abierto y criterios de cierre

1. Recuperar la lista de los ocho cruces desde `candidata-cruces.json` / `extraccion-registro.json`; anotar archivo, línea, símbolo y propietario.
2. Para cada acceso, decidir entre puerto explícito, inversión de dependencia, traslado de responsabilidad o corrección de clasificación. Registrar la justificación y el impacto.
3. Definir o revisar contratos: parámetros de entrada, tipos y esquema de salida, errores, efectos secundarios, idempotencia y compatibilidad.
4. Implementar cambios mínimos por commit y agregar pruebas de contrato y regresión, incluidos fallos del servicio de voz.
5. Ejecutar los controles del repositorio en checkout completo; capturar comandos, resultados, versión de Python y SHA evaluado.
6. Regenerar documentos **solo desde fuentes canónicas**. No editar derivados manualmente ni ampliar baselines para ocultar cruces.
7. Comparar con el otro agente: cambios coincidentes en `vault_servicio.py` y gobernanza, conflictos de diseño y pruebas; resolver antes de cualquier PR/merge.

## 6. Formato obligatorio para siguientes actualizaciones

| Fecha | Paso | Cambio | Archivo(s) | Commit | Pruebas (comando + resultado) | Riesgos / siguiente acción |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-10-24 | 1–4 | Estado inicial de transferencia | Ver secciones 2–4 | `477e412`, `d7b1b4`, `4091f49` | **No ejecutadas** | Analizar puertos y contratos; validar suite |

**Regla:** no marcar «completado» sin distinguir implementación, comprobación estática y pruebas ejecutadas. El tiempo transcurrido no constituye evidencia de progreso.
