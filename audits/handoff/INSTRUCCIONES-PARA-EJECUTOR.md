# Mensaje de QA al agente ejecutor — ronda 1

**De:** QA arquitectónico (ChatGPT). **Para:** agente local. **Estado:** LISTO PARA EJECUTAR. **Rama de referencia:** `audit/archify-governance-20261024`.

## Intención del propietario
Dos agentes colaboran por turnos: QA investiga, traza y planifica; el agente local implementa y verifica en checkout real; QA revisa la evidencia y responde. El propietario transmite avisos entre rondas. **No trabajar en `main`; no asumir que QA ejecutó pruebas.** Método ODD = Organic Driven Development (Gentleman Programming): explorar primero, cambiar poco y validar; preservar contratos y evidencia.

## Trabajo de esta ronda
1. Lee `audits/2026-10-24-plan-maestro-qa-ejecutor.md` y `audits/2026-10-24-bitacora-auditoria-y-handoff.md`.
2. **Q00:** entrega SHA base, estado de git, versión Python, inventario de comandos/controles existentes y logs de baseline. Identifica cualquier diferencia con la rama remota.
3. **Q02:** ejecuta `python -m unittest discover -s tests -p 'test_ap39_contrato.py'`; reporta salida exacta y resultados. No cambies pruebas solo para que pasen.
4. **Q01:** inspecciona `vault_write.py` y `vault_tags.py`. Propon un diff mínimo para los puertos de resolución pura antes de guardar y registro de novedades después. No adelantes el ledger ni modifiques comportamiento sin pruebas de error.
5. **Q03:** inspecciona `vault/ciclo_de_vida/sanacion.py` y `vault_reindex.notas_indexables`; identifica interfaz equivalente o propone puerto, con pruebas para raíz alternativa y filtros.
6. Trabaja en rama auxiliar o worktree y registra los commits. **No hagas merge a main ni sobrescribas el plan o las notas de QA.**

## Respuesta requerida
Escribe tu resultado en `audits/handoff/RESPUESTA-DEL-EJECUTOR.md` (reemplaza plantilla con ronda y evidencia). Usa `ID | SHA base | archivos | commit/diff | comando | salida/resultado | riesgo | pregunta para QA`. Si no puedes ejecutar, registra bloqueo real, no aprobación ficticia. Informa al propietario que la nota está lista para que solicite a QA leerla.

**Criterio de entrega:** evidencia de Q00 y Q02; propuesta fundamentada de Q01 y Q03, con cambios implementados solo si son seguros y aislados. QA decidirá aceptación en `RESPUESTA-QA.md`.
