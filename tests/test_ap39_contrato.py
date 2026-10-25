"""Pruebas de contrato AP-39: resolver antes de escribir, registrar después.

Ejecutar desde la raíz: python -m unittest discover -s tests -p 'test_ap39_contrato.py'
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import vault_tags


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


if __name__ == "__main__":
    unittest.main()
