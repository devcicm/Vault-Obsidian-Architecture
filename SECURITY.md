# Seguridad

## Cómo reportar un fallo

**Usa el reporte privado de GitHub:** pestaña *Security* → *Report a vulnerability*.
Eso abre un canal privado y no publica nada mientras se trabaja en el arreglo.

Si esa vía no te funciona, abre un issue **sin detalles explotables** —solo «tengo
algo de seguridad que reportar»— y se te contesta por dónde seguir. No pongas el
detalle en un issue público.

Este proyecto lo mantiene una persona en su tiempo. No hay SLA. Lo que sí hay es
el compromiso de contestar y de no dejar un reporte sin respuesta.

## Qué modelo de amenaza asume el toolkit

Conviene decirlo antes de que alguien lo descubra en producción, porque varias de
estas cosas **son decisiones de diseño**, no descuidos, y saberlo cambia dónde se
puede instalar esto.

### El servidor MCP es local, sin autenticación, a propósito

`mcp/nodejs/vault-mcp-server.mjs --port <n>` escucha en `127.0.0.1` y **no
comprueba ninguna credencial**. Cualquier proceso de la misma máquina que alcance
ese puerto puede leer y escribir el vault entero.

Es correcto para lo que es —un servidor local para un cliente MCP local— y
peligroso como sorpresa. **Ponerlo detrás de un proxy inverso publica el vault
completo, sin autenticación, a quien alcance el proxy.** Si necesitas acceso
remoto, la autenticación y el TLS los pones tú delante; este servidor no los hace
y no pretende hacerlos.

### El toolkit ejecuta lo que le des

Las tools leen y escriben markdown en el directorio que se les indique, y algunas
invocan `git` como subproceso. Corren con tus permisos. No hay sandbox.

### El contenido del vault es entrada no confiable

`cli/safety.py` (`scan_content`) hace un preflight anti-*poisoning* sobre lo que
entra por `vault_ingest`, y **no es desactivable**. Es una mitigación, no una
garantía: si tu vault va a ser leído por un agente LLM, el contenido del vault es
superficie de ataque —inyección de instrucciones en una nota— y ninguna
herramienta de este repo puede resolver eso por completo.

### Qué NO sale de tu máquina

Nada. Sin base de datos, sin *embeddings*, sin telemetría, sin llamadas de red.
La única dependencia fuera de la stdlib es PyYAML. Esa restricción es la premisa
del proyecto, no una fase pendiente.

## Versiones soportadas

Se arregla sobre la **última versión publicada**. No hay ramas de mantenimiento
para versiones anteriores. La versión vigente la manda
`scripts/vault_version.py` (`CURRENT_VERSION`), nunca un número escrito en un
documento.

## Antes de tocar un vault que no es tuyo

Regla 7 del estándar, y aquí es también una norma de seguridad: mide en **solo
lectura** antes de escribir.

```bash
python scripts/vault_foreign_check.py --root /ruta/al/vault
```

Ninguna tool de escritura debería ejecutarse contra material que no generó este
toolkit sin que su dueño lo pida.
