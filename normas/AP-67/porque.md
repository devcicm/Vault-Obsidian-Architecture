# AP-67 — El material que el agente opera, sin nota que lo apunte

## Por qué existe

El caso llegó de un vault real, y de lo que el caso tenía de más: no fue un
error de una tool, fue un **hueco de la memoria**.

En `Desktop\Agente` se ejecutaron cinco scripts de prueba del motor TTS
(`test-tts-simple.py`, `test-tts-streaming.ps1`, `test-tts-emoji.ps1`,
`test-tts-fix.ps1`, `test-tts-warnings.js`) para comprobar que la
funcionalidad funcionaba. Los resultados sí acabarían en el vault —tres notas
en `02_Observability`—, pero los **scripts** quedaron en la raíz del
repositorio, y el vault no tenía ni una nota que los apuntara: `11_Code`
estaba vacío, el proyecto no estaba registrado, y `vault_code_sync` no decía
nada porque su recorrido solo miraba los ficheros que ya tenían `@vault:`.

La foto del hueco, medida con la herramienta que ya existía:

```
Notas revisadas : 1        <- el scaffold de 11_Code
Sin source_file : 1
Refs huérfanas  : 0        <- nada que mirar: no había nada
```

Un vault puede estar «limpio» y no saber nada. Eso no lo mide ninguna puerta
que hubiera hasta ahora, y por eso la norma nace con una comprobación nueva y
no con una afirmación.

## Lo que se midió, y lo que no

Al直接或 con el vault real, el `audit` de la raíz del proyecto pedía el
contrato de una nota a 18.102 ficheros que no son notas: el `node_modules` de
un proyecto, con sus 274 README. Eso era ruido, y se corrigió en v41.14
(O9). Pero debajo del ruido había dos hechos que sí importaban y que nadie
miraba:

1. El proyecto estaba **enlazado** al vault (`vault_project --link`) y el
   vault **no tenía una sola nota de su código**. Un enlace que no lleva a
   ninguna parte.
2. Los scripts que el agente había ejecutado **no tenían nota**. El trabajo
   se había hecho y no había quedado escrito.

Lo que la norma recoge, entonces, no es «el material debe estar dentro del
vault» —eso ya lo dicen AP-15 y CN-02, y el material de un proyecto no puede
estar dentro de una sección sin que sus README de `node_modules` cuenten como
notas—. Es lo otro: **el vault tiene que saber qué material existe y se
operó**, y para eso el enlace tiene que ir en los dos sentidos.

## Las caras

- **Criterio:** `scripts/vault_code_sync.py::vault_code_sync` — el recorrido
  bidireccional entre las notas de `11_Code` y los ficheros del repositorio.
  Añade dos hallazgos: `proyecto_sin_conocimiento` (un proyecto enlazado sin
  notas de código) y `fuente_sin_nota` (los ficheros del repositorio que
  ninguna nota apunta, con recuento y muestra).
- **Aplica y detecta:** la misma función; los dos hallazgos salen en el
  `summary` y en el informe legible.
- **Heal:** no hay sanador automático, y se dice por qué. La mitad automática
  existe —`vault_code_sync --fix` inyecta el `@vault:` que falta en el
  fichero—, pero la otra mitad (qué material merece nota) es una decisión que
  las tools no pueden tomar: la ejecuta `vault_code_module` o
  `vault_test_save`, con criterio humano o del agente.
- **Tests:** `test_ap67_norma.py`, en este paquete, y
  `tests/test_ap67_conocimiento_del_material.py`.

## Lo que la norma no dice

No dice que el repositorio entero tenga que estar documentado: en un proyecto
real hay 18.102 ficheros y la mayoría no merecen nota. Dice que **lo que el
agente opera** tiene que estar en la memoria, y que la puerta para saberlo es
el enlace en los dos sentidos. Por eso `fuente_sin_nota` se informa con el
recuento y una muestra, y no como un fallo: es un número que dice «de esto,
documentaste tanto», no una lista de 18.000 deudas.
