<!-- propiedad: CARLOS IVAN CM · revisión: manual · revisado: 2026-11-16 -->

# Inventarios portables con vault_insights

`vault_insights` es una utilidad local de inventario y comparacion; no es una tool MCP. El inventario es de solo lectura y usa una identidad persistente para distinguir fuentes sin depender de la ruta donde se encuentre el vault.

## Inicio y uso

Desde el checkout del toolkit, establezca `VAULT_ROOT` apuntando al vault correcto y `VAULT_STRICT_ROOT=1`; confirme la raiz antes de ejecutar operaciones. Inicialice una vez la identidad con `python scripts/vault_insights.py --inicializar-identidad`. Esta operacion explicita crea `00_System/insights-identidad.json`; repetirla conserva la identidad. Un inventario no crea ese archivo: si falta, falla con `IDENTITY_MISSING` y la recuperacion indica `--inicializar-identidad`; si existe pero es ilegible o invalido, falla con `DATA_FILE_CORRUPT` y no se genera otra.

Ejecute `python scripts/vault_insights.py` para consultar o `python scripts/vault_insights.py --guardar <ruta-fuera-del-vault>` para guardar. Compare con `python scripts/vault_insights.py --comparar <captura-a> <captura-b>`. Por defecto un guardado existente no se reemplaza, incluso ante una carrera; `--force` autoriza sobrescritura. La publicacion sin sobrescritura usa hardlinks y falla si el sistema de archivos no los admite; no degrada a una escritura insegura.

## Compatibilidad y limites

Las capturas usan esquema 3. Los snapshots previos de esquema 2 no se convierten ni comparan automaticamente: genere nuevas capturas despues de inicializar la identidad. La comparacion requiere identidad, completitud, criterio de poblacion y recuentos compatibles. Un archivo ilegible o con UTF-8 invalido hace que el inventario sea incompleto. Una coincidencia de contenido duplicado se conserva como alta y baja, sin atribuir un renombrado ambiguo.

La comparacion rechaza capturas con hashes de cuerpo o metadatos que no tengan el formato generado: 16 caracteres hexadecimales minusculos. Esto evita atribuir cambios o renombrados a valores vacios o malformados.

Mover o renombrar el vault conserva su identidad si se conserva el archivo de identidad. Una copia tambien conserva esa identidad: no hay aqui un mecanismo para separar automaticamente clones independientes. No cambie manualmente la identidad de un vault existente para forzar una comparacion. Los hashes y capturas no dan acceso a las fuentes y el resultado no certifica la verdad del contenido.

## Evaluacion del contexto

`tests/test_context_pack_evaluacion.py` contiene dos casos sinteticos etiquetados que miden recuperacion, omisiones y truncado del empaquetado con resultados de busqueda simulados. No evalua busqueda real, no calibra pesos y no demuestra calidad en vaults de terceros. Las pruebas deben ejecutarse en una copia aislada con su propio `vault-sandbox`.
