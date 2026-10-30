"""AP-13 / A-05 — el escaneo solo miraba presencia: `createdAt: ayer` pasaba."""
import pytest

from vault_norms import _timestamp_ap13_valido as valido


@pytest.mark.parametrize("v", ["2026-10-30T12:00:00.000Z", "2026-10-30T12:00:00Z"])
def test_formatos_validos(v):
    assert valido(v)


@pytest.mark.parametrize("v", ["ayer", "2026-10-30", "2026-13-40T99:00:00Z",
                               "2026-10-30T12:00:00+02:00", 20261030, ""])
def test_ap13_formas_invalidas(v):
    assert not valido(v)
