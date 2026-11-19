# Tutorial: tu primer vault en quince minutos

<!-- propiedad: CARLOS IVAN CM · revisión: manual -->

Vas a crear un vault, guardar una decisión técnica, buscarla, cambiarla por
otra sin perder la anterior, preparar el contexto que leería un agente y ver
la historia de lo que pasó. Al final sabrás para qué sirve el producto, y lo
habrás comprobado tú.

No hace falta conocer el estándar. Cada paso dice qué escribir y qué deberías
ver. **Este recorrido lo ejecuta un test** (`tests/test_tutorial_ejecutable.py`)
en cada cambio del repositorio: si un comando deja de funcionar, falla la
puerta antes de que te falle a ti.

## Antes de empezar

Necesitas Python 3.9 o superior y el producto instalado. Si todavía no lo
tienes, sigue [Instalación limpia](INSTALACION-LIMPIA.md) y vuelve aquí. Debe
responder:

```bash
vault --version
```

Los comandos son de `bash` (Linux, o Git Bash o WSL en Windows). En macOS las
tools fallan cerradas a propósito: no hay contención de procesos verificada
(ver el [README](../README.md#estado-del-proyecto--léelo-antes-de-instalar)).
Trabaja en una carpeta vacía.

## 1. Crear el vault

```bash
vault init vault-tutorial
export VAULT_ROOT="$PWD/vault-tutorial"
export VAULT_AGENT=yo
```

`vault init` crea las carpetas del estándar (`03_Decisions`, `07_Knowledge`,
`18_Bugs`...) con un índice y una nota guía en cada una. `VAULT_ROOT` le dice a
las herramientas qué vault usar, y `VAULT_AGENT` firma lo que escribas: toda
escritura lleva autor, y sin él se rechaza en vez de quedar anónima.

## 2. Guardar lo que sabes

Tu equipo publica eventos en Redis. Guárdalo:

```bash
vault run vault_write --folder 07_Knowledge \
  --title "Cola de eventos con Redis" --tags eventos arquitectura \
  --content "$(printf '%s\n' \
    'Los servicios publican sus eventos en una cola de Redis Streams.' \
    'Cada consumidor lee con su propio grupo y confirma lo procesado.' \
    'Elegimos Redis porque ya lo operabamos para la cache de sesiones.')"
```

Deberías ver `"ok": true` y `"path": "07_Knowledge/cola-de-eventos-con-redis.md"`.
Abre ese fichero: es Markdown con un frontmatter YAML (id, autor, fechas,
etiquetas). Lo puedes leer sin el producto, con cualquier editor u Obsidian.

Si escribes una nota de una línea, la escritura se rechaza y la respuesta dice
por qué y cómo seguir (`recovery`): el estándar no deja crear notas a medias
(al menos tres líneas con diez palabras reales).

## 3. Encontrarlo

```bash
vault run vault_search --query "cola de eventos"
```

El primer resultado es tu nota. La búsqueda pondera el título, las etiquetas y
el comienzo del texto; las palabras vacías («de», «la», «the») no cuentan.

## 4. Cambiar de decisión sin perder la anterior

Meses después migráis a NATS. Guarda la nueva verdad y declara que sustituye a
la anterior:

```bash
vault run vault_write --folder 07_Knowledge \
  --title "Cola de eventos con NATS" --tags eventos arquitectura \
  --content "$(printf '%s\n' \
    'Los servicios publican sus eventos en NATS JetStream desde marzo.' \
    'Cada consumidor durable confirma lo procesado y se puede reprocesar.' \
    'Reemplaza a Redis Streams porque necesitabamos retencion por tiempo.')"
vault run vault_supersede --path 07_Knowledge/cola-de-eventos-con-redis.md \
  --by cola-de-eventos-con-nats --apply
```

Nada se borra: la nota de Redis sigue en disco con `superseded_by:` apuntando a
la de NATS. Busca otra vez:

```bash
vault run vault_search --query "cola de eventos"
```

Ahora solo aparece NATS, y la respuesta trae `history_excluded` con
`"superseded": 1`: la búsqueda responde con lo vigente y te dice qué dejó
fuera. Si lo que quieres es la historia:

```bash
vault run vault_search --query "cola de eventos" --incluir-historico
```

## 5. Preparar el contexto para un agente

Un agente no lee el vault entero: pide un paquete con lo relevante dentro de un
presupuesto de tokens.

```bash
vault run vault_context_pack "cola de eventos"
```

El paquete trae las notas vigentes que responden, con la razón de cada una, y
deja fuera la nota sustituida. Es lo que un agente leería al empezar una sesión
para no repetir lo que ya se decidió.

## 6. Ver la historia

Cada operación queda registrada: quién, qué y por qué.

```bash
vault run vault_change_log --query
vault run vault_undo --list 07_Knowledge/cola-de-eventos-con-redis.md
```

El registro de cambios lista las dos notas creadas y la sustitución, con
tu firma; `vault_undo --list` enseña la versión de la nota de Redis de antes
de anotarla, que `vault_undo --restore` recupera como copia sin pisar la
actual.

## 7. Conectar tu agente

```bash
vault mcp-path --root "$VAULT_ROOT"
```

Imprime la entrada que pegas en la configuración MCP de tu cliente (Claude
Code, Cursor...). Desde ahí el agente usa las mismas herramientas que acabas
de usar tú.

## Qué has aprendido

- El conocimiento vive en Markdown legible, con autor y fechas.
- Buscar y armar contexto responde con lo vigente; la historia no se borra, se
  aparta y se puede pedir.
- Cada cambio queda registrado y se puede deshacer.

## Siguiente paso

| Quiero... | Lee |
|---|---|
| Poblar un vault desde un proyecto existente | [Onboarding](MODO-AGENTICO-ONBOARDING.md) |
| Adaptar un vault que ya tenía notas | [Sanación](MODO-AGENTICO-SANACION.md) |
| Ver todas las variables de entorno | [Entorno](ENTORNO.md) |
| Entender qué promete el producto y qué no | [Guía de producción](GUIA-DE-PRODUCCION.md) |
