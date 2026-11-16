<!-- propiedad: CARLOS IVAN CM · revisión: manual -->

# Contrato de descubrimiento del MCP

`vault_registry` y el recurso `vault://registry` conservan sus respuestas
habituales cuando el barrido termina sin errores. Si no se puede recorrer un
subárbol o inspeccionar un candidato, ambas superficies siguen publicando los
vaults que sí se encontraron y añaden `discovery_incomplete`; no presentan ese
conjunto parcial como un inventario completo.

## Respuesta

En una ejecución completa, el envelope mantiene `ok` y `vaults` con los campos
existentes. En una ejecución incompleta, agrega:

```json
{
  "discovery_incomplete": {
    "traversal_failures": 1,
    "candidate_failures": 0,
    "truncated": false
  }
}
```

Los contadores se limitan a 100 por categoría. Si se supera ese límite,
`truncated` pasa a `true`. El diagnóstico no expone rutas, nombres de
directorios ni mensajes del sistema de archivos. Las entradas encontradas y
las ya registradas siguen disponibles; un barrido parcial no las elimina.

## Raíces opcionales

Una raíz de búsqueda configurada que no existe no es un fallo fatal ni marca el
resultado como incompleto. Otros errores de lectura sí se informan en el
resumen, mientras el servidor continúa con las raíces accesibles.
