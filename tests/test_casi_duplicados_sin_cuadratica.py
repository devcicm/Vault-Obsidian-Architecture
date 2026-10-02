"""AP-18: los casi-duplicados se detectan sin comparar todos los pares.

`_detect_near_duplicates` calculaba Jaccard entre cada par de notas: n·(n−1)/2
comparaciones de conjuntos de shingles, la mayoría entre notas que no comparten
ni uno. Con filtrado por prefijo —orden global de shingles por frecuencia, y
dos conjuntos con J ≥ t comparten un shingle en sus prefijos de longitud
|x| − ⌈t·|x|⌉ + 1— solo se verifican los pares que pueden superar el umbral.
El resultado tiene que ser el de la fuerza bruta, par a par y en el mismo orden.
"""

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import vault_graph_inspect as gi  # noqa: E402


def _fuerza_bruta(notes, threshold, exclude_templates):
    shingle_map = {}
    for p in sorted(notes):
        info = notes[p]
        if exclude_templates and any("template" in t for t in info["tags"]):
            continue
        if len(info["body"]) < 100:
            continue
        shingle_map[p] = gi._shingles(info["body"])
    paths = list(shingle_map)
    pares = []
    for i, a in enumerate(paths):
        for b in paths[i + 1 :]:
            sim = gi._jaccard(shingle_map[a], shingle_map[b])
            if sim >= threshold:
                pares.append({"files": [a, b], "similarity": round(sim, 3)})
    return sorted(pares, key=lambda x: -x["similarity"])


def _corpus(semilla, n=60):
    rnd = random.Random(semilla)
    vocab = [f"w{i}" for i in range(40)]
    bases = [[rnd.choice(vocab) for _ in range(60)] for _ in range(6)]
    notes = {}
    for i in range(n):
        palabras = list(rnd.choice(bases))
        for _ in range(rnd.choice([0, 0, 1, 1, 2, 3, 5, 10, 25])):  # de igual a distinta
            palabras[rnd.randrange(len(palabras))] = rnd.choice(vocab)
        tags = {"template"} if i % 11 == 0 else set()
        notes[f"0{i % 3}_S/n{i:03d}.md"] = {"body": " ".join(palabras), "tags": tags}
    return notes


@pytest.mark.parametrize("semilla", range(8))
@pytest.mark.parametrize("threshold", [0.0, 0.3, 0.5, 0.7, 0.8, 0.85, 0.9, 1.0])
def test_ap18_mismo_resultado_que_la_fuerza_bruta(semilla, threshold):
    notes = _corpus(semilla)
    for excluir in (True, False):
        assert gi._detect_near_duplicates(notes, threshold, excluir) == _fuerza_bruta(
            notes, threshold, excluir
        )


def test_ap18_notas_disjuntas_no_se_comparan(monkeypatch):
    notes = {
        f"07_K/n{i:03d}.md": {
            "body": " ".join(f"n{i}p{j}" for j in range(40)),
            "tags": set(),
        }
        for i in range(80)
    }
    llamadas = []
    real = gi._jaccard
    monkeypatch.setattr(gi, "_jaccard", lambda a, b: llamadas.append(1) or real(a, b))
    assert gi._detect_near_duplicates(notes, 0.8, True) == []
    assert llamadas == [], f"{len(llamadas)} comparaciones entre notas sin un shingle en común"
