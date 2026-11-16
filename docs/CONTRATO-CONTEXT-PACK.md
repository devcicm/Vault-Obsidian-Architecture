<!-- propiedad: CARLOS IVAN CM · revisión: manual -->

# Contrato del presupuesto de contexto

`vault_context_pack` incluye las preferencias obligatorias (`must`) antes de
las notas recuperadas. Si la cabecera y todas esas preferencias no caben
íntegras en `budget_tokens`, devuelve `INVALID_BUDGET` sin entregar un contexto
parcial que pudiera omitir una restricción. Cuando caben, selecciona las notas
según el presupuesto restante y explica las exclusiones en `excluded`.

Si una búsqueda o su reintento falla, `warnings` conserva el código del error
sin copiar mensajes arbitrarios que puedan contener rutas locales. Una búsqueda
que declara resultados incompletos también produce una advertencia: ausencia de
resultados e información incompleta no son equivalentes.

Cuando la recuperación usa el índice de búsqueda, la comprobación contrasta las
rutas y las huellas SHA-256 de los bytes de las notas con las entradas del
índice. Un índice anterior sin huellas tiene frescura no verificada: se
recomienda ejecutar `vault_reindex`, pero la consulta no lo reconstruye. Un
fallo de lectura o una modificación detectada durante la lectura deja la
verificación incompleta; las advertencias no incluyen rutas privadas.

La comprobación recorre el vault y lee las notas indexadas en cada búsqueda
indexada; el empaquetado realiza además su propia comprobación. El tiempo y el
volumen leído dependen de la cantidad y tamaño de las notas y del almacenamiento;
no hay una latencia garantizada. La búsqueda directa en vivo no usa esta
comprobación. Detectar cambios durante cada lectura no constituye una instantánea
atómica de todo el vault. La coherencia del índice de búsqueda no demuestra la
integridad ni la actualidad del grafo, que se comprueba por separado.

Cada entrada reconstruida o refrescada puede incluir `timestamps`: las fechas
de creación y actualización declaradas en el frontmatter se conservan por
separado del tiempo de modificación observado en el filesystem, expresado en
UTC. Una fecha declarada ausente queda en `null`; el tiempo observado no prueba
cuándo se creó la nota ni reemplaza un dato histórico ausente. Los índices
antiguos no se reescriben automáticamente para añadir estos campos.

La evaluación con búsqueda real comprueba recuperación, resultados vacíos,
truncado y preferencias; no determina cuál de dos fuentes contradictorias es
verdadera ni calibra automáticamente los pesos. La opción `--no-preferences`
omite explícitamente las preferencias del paquete.
