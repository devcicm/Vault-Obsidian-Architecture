# Recibos del colector QG-00..QG-06: candidato e101004 (R26, v41.25)

Ejecucion: `python audits/fase2/colector_qg.py --sha e10100476b3a8bdc2298d7e9acfc9d8f4c494a7a --ejecutar ...`
el 2026-10-29, en una sesion de Claude Code (Windows 10, Python 3.14), con el arbol limpio en ese SHA.
Las rutas de la maquina se normalizan (`<repo>`, `<python>`, `<recibos-base>`, `<sandbox-e2e>`, `<tmp>`, `<user>`). El sha256 de cada
fichero es el del ORIGINAL, antes de normalizar. `colector.json`/`colector.log` son `qg2.json`/`colector2.log` de la segunda corrida.

Resultado: QG-00..QG-06 PASS. Suite: 6501 tests, 6485 passed, 16 skipped, 0 failed, 0 errores (`-n 4`).
CI sobre e101004: run 40843103452, `success`, 27 jobs (ver limites). `release_authorized` sigue en false: lo firma el propietario.

## Como se llego aqui (nada de esto se borra)

- Primera corrida del colector: QG-00/01/02/04/06 PASS; QG-03 NOT_RUN (faltaba `suite.xml.procedencia.json`, el recibo de
  procedencia de la suite) y QG-05 NOT_RUN (no existia el runtime de paridad). Recibos de esa corrida: `recibos/` del directorio de trabajo, no versionados.
- Segunda corrida: se creo la procedencia de la suite (sha del commit, exit 0, sha256 del JUnit de la corrida de la suite sobre el arbol limpio
  en ese SHA) y un runtime real con `vault init`; `vault-backups` (directorio ajeno, hallazgo de entorno AP-36) se aparto y se devolvio a su nombre.
  QG-00..06 PASS.

## Limites declarados

- Suite en Windows con `-n 4`; con `-n auto` el worker `gw1` se cae en `tests/test_noop_audit.py` (causa sin determinar, sin bisecar mas).
- La CI de e101004 tuvo un fallo en el primer intento: `Validate Vault Spec (windows-latest, 3.9, 2)` en `tests/test_naturalezas.py`. El diff de ese commit
  solo tocaba `.archify/`; el job se relanzo y paso (run 40843103452, conclusion success). Es un flaky no diagnosticado, no una excepcion aceptada.
- El colector consulto la CI con `gh` decodificado en cp1252 y devolvio `MATRIZ_INCOMPLETA` por los nombres de job con acento
  (`estÃ¡ndar`). Es un defecto del colector en Windows, corregido despues (UTF-8 explicito en `_gh_json`); con la correccion `estado_ci` da `success`.
  `colector.json` conserva el valor erroneo tal como salio.
- La ejecucion de la paridad (QG-05) regenera `matriz-paridad-cli-mcp.md` y `logs/L3-paridad-cli-mcp.txt`; esos ficheros versionados son los de R25 y no se tocaron.
- macOS fuera de alcance; Linux y Python 3.9-3.12 cubiertos por la CI.

| Fichero | sha256 del original | Nota |
|---|---|---|
| `QG-00.arbol_limpio.json` | `99cda91a1c023100018b3e4472f06a61ed8eda814b9960b23b24a0b60b220504` | versionado (rutas normalizadas) |
| `QG-00.identidad_git.json` | `6b37fa85edb0552cfa24017720ab690d2fc2f05a2b03ef4720ad6467a53a6e3e` | versionado (rutas normalizadas) |
| `QG-00.recibo.json` | `6c7f2dbdfc7f976110e63a40a923fe5e29aef2b4f0e0024e86b6718e0bd2c023` | versionado (rutas normalizadas) |
| `QG-00.reconciliador_archify.salida.txt` | `7448760fa41bafa3b15854357bff4bc8735d0b7492deb4d51c5cab2cb8371ae4` | versionado (rutas normalizadas) |
| `QG-00.saneamiento.salida.txt` | `2a088c40366977da2fdd35b50781d1bd79f7ee16a634800d092176293a0b9ac2` | versionado (rutas normalizadas) |
| `QG-00.subchecks.json` | `4b13274e959d9523fb43916b7c333b137aab691129becfd67b8ad00e88c71c66` | versionado (rutas normalizadas) |
| `QG-01.recibo.json` | `9172e79aa53fe801cf3b192ae1d55e819345e08f7db498b622bf51aaab498b00` | versionado (rutas normalizadas) |
| `QG-01.reconciliador_archify.salida.txt` | `7448760fa41bafa3b15854357bff4bc8735d0b7492deb4d51c5cab2cb8371ae4` | versionado (rutas normalizadas) |
| `QG-01.subchecks.json` | `2bdd0a010dce8cb5f66cfe2f9ac43a0e36df50318afa97d12baf0b05864dc2e9` | versionado (rutas normalizadas) |
| `QG-01.vault_arch.salida.txt` | `24897bc01a1ea1ab3832f2db5756a9a287ccbea461a3f30e5273105bed38b8ff` | versionado (rutas normalizadas) |
| `QG-02.auditoria_completa.salida.txt` | `2f54afcafed46140a76577607328a409dea675c82e4b9f038d91f579c6693230` | versionado (rutas normalizadas) |
| `QG-02.certificacion_compuesta.json` | `e8c52892365938c303b82d9f22314ee74ac7a9b66be5e9d3fc914c59b171989c` | versionado (rutas normalizadas) |
| `QG-02.puertas_26.salida.txt` | `f2f1e72e573b7c44eb7a97301a6c55180640f112d4c88d284f39d4ca8f5c3242` | versionado (rutas normalizadas) |
| `QG-02.recibo.json` | `9dc980cb196593c10d60fb590627e8c995cea232486a8f55986b62af0433ea39` | versionado (rutas normalizadas) |
| `QG-02.subchecks.json` | `01d350ffdedcfb658b4ee43bb2c954a6ae91d59b69cba899df55059c42e26ca3` | versionado (rutas normalizadas) |
| `QG-03.recibo.json` | `bac0601cd2c65665d98739f30437f404e71f4a96757ed5d05650b32e81639c77` | versionado (rutas normalizadas) |
| `QG-03.subchecks.json` | `1b882f6a98bf82a043397d4493d1113298f1e243e0c5b66c0cef71e69054f57f` | versionado (rutas normalizadas) |
| `QG-04.contencion.salida.txt` | `4b950891a4a75b179d08acabe6dfc2bbf5ff652a1b1ce2fbeed41707daf47c4e` | versionado (rutas normalizadas) |
| `QG-04.operaciones_destructivas.salida.txt` | `fc81608fa0ffe8d955d54d4084550fdd585c14b95eff7a7e5b9692f38c03a114` | versionado (rutas normalizadas) |
| `QG-04.pip_audit.salida.txt` | `080dab9672ec31adf1315976d15d2269e61a2e52ca26dd2a68564775d552cc82` | versionado (rutas normalizadas) |
| `QG-04.recibo.json` | `924f8f2640287246d555f22727721547aaa1654587b845c053653757a4e9a866` | versionado (rutas normalizadas) |
| `QG-04.saneamiento.salida.txt` | `2a088c40366977da2fdd35b50781d1bd79f7ee16a634800d092176293a0b9ac2` | versionado (rutas normalizadas) |
| `QG-04.subchecks.json` | `64b53d847cb369c7236f27ee627a8cf139d8cd055df1be5c6a984a382509530c` | versionado (rutas normalizadas) |
| `QG-05.ap40_contrato.salida.txt` | `28218e082e3ba66b2da5fdce90d0bdcb1cb6be78fed20f8020b890dd015453d2` | versionado (rutas normalizadas) |
| `QG-05.paridad_cli_mcp.salida.txt` | `2dcc78ff0fbad78a652810af3b8d34166d069d778466996e420d1df4f6932c0c` | versionado (rutas normalizadas) |
| `QG-05.recibo.json` | `4c64d8fd225922fcb3b4690eb3ea109e90310b12207ef1ec04a09293e409572d` | versionado (rutas normalizadas) |
| `QG-05.subchecks.json` | `d787a8ddee8e129befbcb1b4ac9d00ae536f93dac897632709e1c011e6d6ae45` | versionado (rutas normalizadas) |
| `QG-06.construccion.salida.txt` | (no versionado) | log de build |
| `QG-06.recibo.json` | `1ac41b79683bb21cb40de02cd15ca0bb7ba3c3f1f0a5dc8ae14c42506e444daf` | versionado (rutas normalizadas) |
| `QG-06.subchecks.json` | `a55fdb0fd1aa613bbd1675addacbd6fd608d2f44cd67f056308b1dc1dba681f6` | versionado (rutas normalizadas) |
| `QG-06.wheel_contenido.json` | `f512b1eeea80e1c3a92525feac4f79a113e1208021b04e37db2e304e2b792f70` | versionado (rutas normalizadas) |
| `e2e.json` | `268b7fb8cc04f8f2b977378e437373fffc985708af2a1d360ca1d7158cb6b8d9` | versionado (rutas normalizadas) |
| `colector.log` | `253e05221684e2290ec366fbb6ebbaa47fe44dd6bd68f071de53f31380cc750d` | versionado (rutas normalizadas) |
| `colector.json` | `16c4a3ae6a8cd7aa06ba68aca3a37bd03246680dcef18eefb95e4b80ac5a5df4` | versionado (rutas normalizadas) |
| `junit.xml.procedencia.json` | `87e1268648806a5d9d94741496a1fd1676d9ed768e193f5db5c4502f40a75c34` | versionado (rutas normalizadas) |
| `junit.xml` | `e1e000d4fa04be7821aecf4c81ab2d8c71bd3df0ed65b6b5d778e9a694f60c55` | NO VERSIONADO: JUnit completo: sha256 en junit.xml.procedencia.json |
