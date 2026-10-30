"""B-03 — la CI corre también sobre el tag de release.

`release.yml` exige que la CI certificada sea la del `product_sha`, pero el
tag `v*` apunta a un descendiente documental: sin disparador por tags, el
commit que de verdad se publica nunca pasaba por la CI.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_vault_ci_se_dispara_con_los_tags_de_release():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "vault-ci.yml")
                        .read_text(encoding="utf-8"))
    on = wf.get("on", wf.get(True))  # PyYAML lee `on:` como True
    assert "v*" in (on["push"].get("tags") or []), on["push"]
