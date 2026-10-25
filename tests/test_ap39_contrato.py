"""Pruebas de contrato AP-39: resolver antes de escribir, registrar después.

Ejecutar desde la raíz: python -m unittest discover -s tests -p 'test_ap39_contrato.py'

Los tres casos de la clase `ContratoEscrituraAp39` ejercitan la ruta completa
de `vault_write` contra un vault temporal real (criterio del consumidor, no
mocks del borde): escritura fallida que no deja términos en la bitácora,
escritura exitosa que registra una sola vez, y fallo de la bitácora que no
tumba una nota ya persistida. Auditoría 2026-10-24, ronda 1 (Q02).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import vault_tags

#: `<vault>/19_Audits/vocabulary/tag-ledger.json` — la bitácora append-only
#: (dueño: `vault/indices/repositorio.py`, `dir_vocabulario`).
LEDGER_REL = Path("19_Audits") / "vocabulary" / "tag-ledger.json"

#: El mismo arranque que el Quick Start usa para `vault init`: sin la raíz del
#: repo en PYTHONPATH, el subprocess podía resolver una wheel instalada y
#: medir otro código.
INIT = ("import sys; from vault.product_cli import main; "
        "sys.exit(main(sys.argv[1:]))")


class ContratoVocabulario(unittest.TestCase):
    def test_resolver_no_registra_terminos(self):
        with patch.object(vault_tags, "_canonical_index", return_value={}), \
             patch.object(vault_tags, "resolve_tag", return_value=("ejemplo", "new")), \
             patch.object(vault_tags, "record_new_tags") as registrar:
            canonicos, nuevos = vault_tags.apply_vocabulary(["Ejemplo"])
        self.assertEqual(canonicos, ["ejemplo"])
        self.assertEqual(nuevos[0]["tag"], "ejemplo")
        registrar.assert_not_called()

    def test_registro_vacio_no_escribe(self):
        with patch.object(vault_tags, "atomic_write_json") as escribir:
            self.assertEqual(vault_tags.record_new_tags([]), 0)
        escribir.assert_not_called()

    def test_registro_no_duplica_etiquetas(self):
        from contextlib import nullcontext
        ledger = {"entries": [{"tag": "existente"}]}
        with patch.object(vault_tags, "_vocab_dir") as directorio, \
             patch.object(vault_tags, "_tag_ledger", return_value=Path("/tmp/ledger.json")), \
             patch.object(vault_tags, "file_lock", return_value=nullcontext()), \
             patch.object(vault_tags, "load_ledger", return_value=ledger), \
             patch.object(vault_tags, "utcnow", return_value="2026-10-24T00:00:00Z"), \
             patch.object(vault_tags, "atomic_write_json") as escribir:
            self.assertEqual(vault_tags.record_new_tags([{"tag": "existente"}]), 0)
        escribir.assert_not_called()


class ContratoEscrituraAp39(unittest.TestCase):
    """La ruta completa de `vault_write`, con vault real y subprocess."""

    CONTENIDO = ("Nota de contrato AP-39 para la auditoria del 2026-10-24.\n"
                 "La resolucion del vocabulario ocurre antes de persistir\n"
                 "y el registro append-only despues de la escritura,\n"
                 "con suficiente cuerpo para el gate de contenido.")

    @classmethod
    def setUpClass(cls):
        cls.padre = Path(tempfile.mkdtemp(prefix="ap39-vault-"))
        cls.vault = cls.padre / "vault-audit"
        cls.env = dict(
            os.environ, PYTHONIOENCODING="utf-8", VAULT_ROOT=str(cls.vault),
            VAULT_STRICT_ROOT="1", VAULT_AGENT="agente-ejecutor",
            PYTHONPATH=os.pathsep.join(
                [str(ROOT), *filter(None, [os.environ.get("PYTHONPATH")])]))
        p = subprocess.run(
            [sys.executable, "-c", INIT, "init", str(cls.vault)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=cls.env, cwd=cls.padre, timeout=600)
        sobre = json.loads(p.stdout or "{}")
        assert sobre.get("ok") is True, p.stdout[-600:] + p.stderr[-600:]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.padre, ignore_errors=True)

    def _escribir(self, titulo, tags, con_agente=True, carpeta="00_System"):
        """Una invocación real del CLI de escritura; devuelve el envelope."""
        env = dict(self.env)
        if not con_agente:
            env.pop("VAULT_AGENT", None)
        argv = [sys.executable, str(ROOT / "scripts" / "vault_write.py"),
                "--folder", carpeta, "--title", titulo,
                "--meta", '{"type":"identity"}',
                "--content", self.CONTENIDO]
        if tags:
            argv += ["--tags", ",".join(tags)]
        p = subprocess.run(argv, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           env=env, cwd=self.padre, timeout=600)
        return json.loads(p.stdout or "{}"), p

    def _ledger(self):
        ruta = self.vault / LEDGER_REL
        if not ruta.exists():
            return None
        return json.loads(ruta.read_text(encoding="utf-8"))

    def test_escritura_fallida_no_deja_tags_en_el_ledger(self):
        """Sin autor (AP-16), la escritura se rechaza DESPUÉS de resolver el
        vocabulario: si el orden del write path fuera el contrario, el término
        quedaría en la bitácora como memoria de una nota que nunca existió.
        En carpeta de contenido — `00_System` está exento del guard."""
        tag = "termino-fantasma-ap39"
        sobre, p = self._escribir("AP39 Escritura Fallida", [tag],
                                  con_agente=False, carpeta="07_Knowledge")
        self.assertFalse(sobre.get("ok", True), p.stdout[-600:])
        self.assertEqual(sobre.get("error_code"), "missing_agent",
                         p.stdout[-600:])
        ledger = self._ledger()
        entradas = [e for e in (ledger or {}).get("entries", [])
                    if e.get("tag") == tag]
        self.assertEqual(entradas, [])

    def test_escritura_exitosa_registra_una_sola_vez(self):
        """La escritura confirmada anota el término exactamente una vez, con
        la nota como primer testigo; reescribirla no lo duplica."""
        tag = "termino-exitoso-ap39"
        sobre, p = self._escribir("AP39 Escritura Exitosa", [tag])
        self.assertTrue(sobre.get("ok"), p.stdout[-600:])
        nota = Path(sobre["path"])
        if not nota.is_absolute():
            nota = self.vault / sobre["path"]
        self.assertTrue(nota.is_file(), sobre)
        ledger = self._ledger()
        self.assertIsNotNone(ledger, "la bitácora no se escribió")
        entradas = [e for e in ledger.get("entries", [])
                    if e.get("tag") == tag]
        self.assertEqual(len(entradas), 1)
        self.assertIn("ap39", entradas[0].get("first_note", ""))
        # La reescritura (mismo título, camino update) no añade una segunda
        # entrada: la deduplicación del ledger vale en la ruta completa.
        sobre2, p2 = self._escribir("AP39 Escritura Exitosa", [tag])
        self.assertTrue(sobre2.get("ok"), p2.stdout[-600:])
        entradas2 = [e for e in self._ledger().get("entries", [])
                     if e.get("tag") == tag]
        self.assertEqual(len(entradas2), 1)

    def test_fallo_del_ledger_no_tumba_la_nota(self):
        """La bitácora ilegible/inescribible se registra (`recorded: -1`) y la
        nota ya persistida sobrevive: el ledger es memoria, no candado."""
        tag = "termino-con-ledger-roto-ap39"
        vocab = self.vault / "19_Audits" / "vocabulary"
        shutil.rmtree(vocab, ignore_errors=True)
        vocab.write_text("no es un directorio a propósito", encoding="utf-8")
        sobre, p = self._escribir("AP39 Ledger Roto", [tag])
        self.assertTrue(sobre.get("ok"), p.stdout[-600:])
        nota = Path(sobre["path"])
        if not nota.is_absolute():
            nota = self.vault / sobre["path"]
        self.assertTrue(nota.is_file(), sobre)
        self.assertFalse((self.vault / LEDGER_REL).exists())


if __name__ == "__main__":
    unittest.main()

