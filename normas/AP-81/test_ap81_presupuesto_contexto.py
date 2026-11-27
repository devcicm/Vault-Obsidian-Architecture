"""Tests de paquete de la ID norma AP-81 (offloading a puntero y hard caps)."""

from pathlib import Path
import tempfile
import pytest

from vault.kernel.presupuesto_contexto import (
    HARD_CAPS_CONTEXTO,
    compactar_observaciones,
    offload_texto_a_puntero,
)


def test_ap81_offload_respeta_ap36_y_ahorra_tokens():
    with tempfile.TemporaryDirectory() as td:
        tmp_path = Path(td)
        vault = tmp_path / "vault"
        vault.mkdir()
        grande = "linea de salida de prueba con detalle extenso\n" * 200
        res = offload_texto_a_puntero(
            grande,
            etiqueta="pytest",
            offload_dir=vault / "00_System" / "context-offload",
            vault_root=vault,
        )
        assert res["written"] is True
        assert res["pointer_tokens"] <= 25
        assert res["saved_tokens"] > 1000
        assert (vault / res["ref"]).is_file()

        # Contención AP-36: offload fuera del vault falla cerrado
        with pytest.raises(ValueError, match="AP-36"):
            offload_texto_a_puntero(grande, offload_dir=tmp_path / "fuera", vault_root=vault)


def test_ap81_hard_cap_observaciones():
    obs = [{"id": f"o{i}", "tool": "read", "content": "x" * 100} for i in range(40)]
    res = compactar_observaciones(obs, tokens_usados=1000, ventana_maxima=10000)
    assert len(res["observations"]) == HARD_CAPS_CONTEXTO["max_retained_observations"]
