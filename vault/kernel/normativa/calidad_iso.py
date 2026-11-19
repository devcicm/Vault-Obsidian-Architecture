"""SQuaRE (ISO/IEC 25000) and ISO/IEC/IEEE 29119 vocabularies, declared once.

Kernel leaf: imports nothing from `vault_*`, only the standard library. It
declares; the tools that write requirement and test notes validate against it,
and `vault_quality_check --iso-quality` reports with it.

What lives here and why
-----------------------
- `PRODUCT_QUALITY`: the ISO/IEC 25010:2023 product quality model, nine
  characteristics with their subcharacteristics (owner decision S9: the 2023
  edition). The 2011 names (`usability`, `portability`, `maturity`, ...) and
  the Spanish wording of the user's `isos.txt` resolve as aliases, so neither
  edition is rejected.
- `QUALITY_IN_USE`: the ISO/IEC 25019:2023 quality-in-use model (five
  characteristics). It is a separate vocabulary because its names collide
  with the product model (`efficiency`, `flexibility`).
- `DATA_QUALITY_25012`: the fifteen ISO/IEC 25012 data quality
  characteristics mapped to the framework registries that already measure
  the vault's data (`FUNDAMENTALS`, `CIA_TRIAD`, `FAIR_PRINCIPLES`). An empty
  mapping is a declared gap, never an omission.
- `EVALUATION_25040`: the evaluation process steps mapped to the tools that
  record each step, with the part that stays outside the product.
- `TEST_LEVELS` / `TEST_KINDS` (29119-1), `TEST_PROCESSES` (29119-2),
  `TEST_TECHNIQUES` (29119-4).

Notes that do not declare these fields are untouched: every field built on
these vocabularies is optional and additive.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# ISO/IEC 25010:2023 — product quality model
# ──────────────────────────────────────────────────────────────────────────────

PRODUCT_QUALITY_EDITION = "ISO/IEC 25010:2023"
QUALITY_IN_USE_EDITION = "ISO/IEC 25019:2023"

PRODUCT_QUALITY: List[Dict[str, Any]] = [
    {
        "id": "functional_suitability",
        "name": "Functional suitability",
        "subcharacteristics": ["functional_completeness", "functional_correctness",
                               "functional_appropriateness"],
        "aliases": ["adecuacion_funcional"],
    },
    {
        "id": "performance_efficiency",
        "name": "Performance efficiency",
        "subcharacteristics": ["time_behaviour", "resource_utilization", "capacity"],
        "aliases": ["eficiencia_de_desempeno", "time_behavior"],
    },
    {
        "id": "compatibility",
        "name": "Compatibility",
        "subcharacteristics": ["co_existence", "interoperability"],
        "aliases": ["compatibilidad"],
    },
    {
        "id": "interaction_capability",
        "name": "Interaction capability",
        "subcharacteristics": ["appropriateness_recognizability", "learnability", "operability",
                               "user_error_protection", "user_engagement", "inclusivity",
                               "user_assistance", "self_descriptiveness"],
        # 2011: usability.
        "aliases": ["usability", "usabilidad", "capacidad_de_interaccion"],
    },
    {
        "id": "reliability",
        "name": "Reliability",
        "subcharacteristics": ["faultlessness", "availability", "fault_tolerance", "recoverability"],
        "aliases": ["fiabilidad"],
    },
    {
        "id": "security",
        "name": "Security",
        "subcharacteristics": ["confidentiality", "integrity", "non_repudiation", "accountability",
                               "authenticity", "resistance"],
        "aliases": ["seguridad"],
    },
    {
        "id": "maintainability",
        "name": "Maintainability",
        "subcharacteristics": ["modularity", "reusability", "analysability", "modifiability",
                               "testability"],
        "aliases": ["mantenibilidad"],
    },
    {
        "id": "flexibility",
        "name": "Flexibility",
        "subcharacteristics": ["adaptability", "scalability", "installability", "replaceability"],
        # 2011: portability.
        "aliases": ["portability", "portabilidad", "flexibilidad"],
    },
    {
        "id": "safety",
        "name": "Safety",
        "subcharacteristics": ["operational_constraint", "risk_identification", "fail_safe",
                               "hazard_warning", "safe_integration"],
        "aliases": [],
    },
]

#: 2011 subcharacteristic names renamed in 2023.
PRODUCT_SUBCHARACTERISTIC_ALIASES: Dict[str, str] = {
    "maturity": "faultlessness",
    "user_interface_aesthetics": "user_engagement",
    "accessibility": "inclusivity",
    "analyzability": "analysability",
}

# ──────────────────────────────────────────────────────────────────────────────
# ISO/IEC 25019:2023 — quality-in-use model
# ──────────────────────────────────────────────────────────────────────────────

QUALITY_IN_USE: List[Dict[str, Any]] = [
    {"id": "effectiveness", "name": "Effectiveness", "subcharacteristics": [],
     "aliases": ["efectividad"]},
    {"id": "efficiency", "name": "Efficiency", "subcharacteristics": [],
     "aliases": ["eficiencia"]},
    {"id": "satisfaction", "name": "Satisfaction",
     "subcharacteristics": ["usefulness", "trust", "pleasure", "comfort"],
     "aliases": ["satisfaccion"]},
    {"id": "freedom_from_risk", "name": "Freedom from risk",
     "subcharacteristics": ["economic_risk_mitigation", "health_and_safety_risk_mitigation",
                            "environmental_and_societal_risk_mitigation"],
     "aliases": ["libertad_de_riesgo"]},
    {"id": "context_coverage", "name": "Context coverage",
     "subcharacteristics": ["context_completeness", "flexibility"],
     "aliases": ["cobertura_de_contexto"]},
]

QUALITY_IN_USE_SUBCHARACTERISTIC_ALIASES: Dict[str, str] = {
    "environmental_risk_mitigation": "environmental_and_societal_risk_mitigation",
}

#: Model name -> (characteristics, subcharacteristic aliases, frontmatter field).
QUALITY_MODELS: Dict[str, Tuple[List[Dict[str, Any]], Dict[str, str], str]] = {
    "product": (PRODUCT_QUALITY, PRODUCT_SUBCHARACTERISTIC_ALIASES, "quality_characteristics"),
    "in_use": (QUALITY_IN_USE, QUALITY_IN_USE_SUBCHARACTERISTIC_ALIASES, "quality_in_use"),
}

# ──────────────────────────────────────────────────────────────────────────────
# ISO/IEC 25012 — data quality model, mapped to the framework registries
# ──────────────────────────────────────────────────────────────────────────────

#: `framework` names ids of `FUNDAMENTALS`, `CIA_TRIAD` or `FAIR_PRINCIPLES`
#: (vault_fundamentals_catalog). Empty means nothing in the toolkit measures it.
DATA_QUALITY_25012: List[Dict[str, Any]] = [
    {"id": "accuracy", "point_of_view": "inherent", "framework": ["F4"]},
    {"id": "completeness", "point_of_view": "inherent", "framework": ["F3", "F1"]},
    {"id": "consistency", "point_of_view": "inherent", "framework": ["F2"]},
    {"id": "credibility", "point_of_view": "inherent", "framework": ["F7"]},
    {"id": "currentness", "point_of_view": "inherent", "framework": ["F6"]},
    {"id": "accessibility", "point_of_view": "both", "framework": ["FAIR-A"]},
    {"id": "compliance", "point_of_view": "both", "framework": ["F5"]},
    {"id": "confidentiality", "point_of_view": "both", "framework": ["CIA-C"]},
    {"id": "efficiency", "point_of_view": "both", "framework": []},
    {"id": "precision", "point_of_view": "both", "framework": []},
    {"id": "traceability", "point_of_view": "both", "framework": ["F8"]},
    {"id": "understandability", "point_of_view": "both", "framework": ["FAIR-I"]},
    {"id": "availability", "point_of_view": "system_dependent", "framework": ["CIA-A"]},
    {"id": "portability", "point_of_view": "system_dependent", "framework": ["FAIR-A"]},
    {"id": "recoverability", "point_of_view": "system_dependent", "framework": ["CIA-A"]},
]

# ──────────────────────────────────────────────────────────────────────────────
# ISO/IEC 25040 — evaluation process
# ──────────────────────────────────────────────────────────────────────────────

EVALUATION_25040: List[Dict[str, Any]] = [
    {"id": "establish_evaluation_requirements",
     "record": "Requirements declare the 25010/25019 characteristics they specify",
     "tools": ["vault_requirement_save"], "outside_product": None},
    {"id": "specify_evaluation",
     "record": "Measure: share of declared requirements with at least one test, per characteristic",
     "tools": ["vault_quality_check"], "outside_product": None},
    {"id": "design_evaluation",
     "record": "Test cases with level, type and design technique (29119-1/-4)",
     "tools": ["vault_test_save"],
     "outside_product": "The evaluation plan as an approved document"},
    {"id": "execute_evaluation",
     "record": "Test results recorded on each case (pass/fail/blocked/skip)",
     "tools": ["vault_test_save", "vault_test_runner"], "outside_product": None},
    {"id": "conclude_evaluation",
     "record": "Coverage report per characteristic; nonconformities as NCR",
     "tools": ["vault_quality_check", "vault_ncr_save"],
     "outside_product": "Objective evaluation and certification by an independent third party"},
]

# ──────────────────────────────────────────────────────────────────────────────
# ISO/IEC/IEEE 29119-1:2022 — test levels and test types
# ──────────────────────────────────────────────────────────────────────────────

TEST_LEVELS: List[Dict[str, Any]] = [
    {"id": "component", "aliases": ["unit", "unit_testing", "component_testing"]},
    {"id": "integration", "aliases": ["integration_testing", "component_integration"]},
    {"id": "system", "aliases": ["system_testing", "e2e", "end_to_end"]},
    {"id": "system_integration", "aliases": ["system_integration_testing"]},
    {"id": "acceptance", "aliases": ["acceptance_testing", "uat"]},
]

#: Quality-related test types of 29119-1. Named `test_kinds` in the
#: frontmatter because `test_type` is already the folder vocabulary of
#: `15_Tests/` (unit, integration, e2e, performance, security, acceptance).
TEST_KINDS: List[Dict[str, Any]] = [
    {"id": "functional", "aliases": []},
    {"id": "accessibility", "aliases": []},
    {"id": "backup_recovery", "aliases": ["backup_and_recovery"]},
    {"id": "compatibility", "aliases": []},
    {"id": "conversion", "aliases": ["migration"]},
    {"id": "disaster_recovery", "aliases": []},
    {"id": "installability", "aliases": []},
    {"id": "interoperability", "aliases": []},
    {"id": "localization", "aliases": ["localisation"]},
    {"id": "maintainability", "aliases": []},
    {"id": "performance", "aliases": ["load", "stress", "endurance", "volume", "capacity"]},
    {"id": "portability", "aliases": []},
    {"id": "procedure", "aliases": []},
    {"id": "reliability", "aliases": []},
    {"id": "security", "aliases": []},
    {"id": "usability", "aliases": []},
]

#: The pre-29119-1 `test_type` folder vocabulary, read as (level, kind).
LEGACY_TEST_TYPE: Dict[str, Tuple[Optional[str], Optional[str]]] = {
    "unit": ("component", None),
    "integration": ("integration", None),
    "e2e": ("system", None),
    "acceptance": ("acceptance", None),
    "performance": (None, "performance"),
    "security": (None, "security"),
}

# ──────────────────────────────────────────────────────────────────────────────
# ISO/IEC/IEEE 29119-2:2021 — test processes
# ──────────────────────────────────────────────────────────────────────────────

TEST_PROCESSES: List[Dict[str, Any]] = [
    {"id": "organizational_test_process", "layer": "organizational", "tools": [],
     "outside_product": "Test policy and organizational test practices are the organization's"},
    {"id": "test_planning", "layer": "management", "tools": [],
     "outside_product": "No typed test plan record; the plan is the organization's document"},
    {"id": "test_monitoring_and_control", "layer": "management",
     "tools": ["vault_quality_check"], "outside_product": None},
    {"id": "test_completion", "layer": "management", "tools": ["vault_quality_check"],
     "outside_product": "The completion report as an approved document"},
    {"id": "test_design_and_implementation", "layer": "dynamic",
     "tools": ["vault_test_save"], "outside_product": None},
    {"id": "test_environment_set_up_and_maintenance", "layer": "dynamic",
     "tools": ["vault_env_matrix"], "outside_product": None},
    {"id": "test_execution", "layer": "dynamic",
     "tools": ["vault_test_save", "vault_test_runner"], "outside_product": None},
    {"id": "test_incident_reporting", "layer": "dynamic",
     "tools": ["vault_bug_save"], "outside_product": None},
]

# ──────────────────────────────────────────────────────────────────────────────
# ISO/IEC/IEEE 29119-4:2021 — test design techniques
# ──────────────────────────────────────────────────────────────────────────────

TEST_TECHNIQUES: List[Dict[str, Any]] = [
    # Specification-based (black-box).
    {"id": "equivalence_partitioning", "category": "specification_based", "aliases": []},
    {"id": "classification_tree_method", "category": "specification_based",
     "aliases": ["classification_tree"]},
    {"id": "boundary_value_analysis", "category": "specification_based",
     "aliases": ["boundary_value"]},
    {"id": "syntax_testing", "category": "specification_based", "aliases": []},
    {"id": "combinatorial_testing", "category": "specification_based",
     "aliases": ["pairwise", "pairwise_testing"]},
    {"id": "decision_table_testing", "category": "specification_based", "aliases": []},
    {"id": "cause_effect_graphing", "category": "specification_based", "aliases": []},
    {"id": "state_transition_testing", "category": "specification_based", "aliases": []},
    {"id": "scenario_testing", "category": "specification_based",
     "aliases": ["use_case", "use_case_testing"]},
    {"id": "random_testing", "category": "specification_based", "aliases": []},
    {"id": "metamorphic_testing", "category": "specification_based", "aliases": []},
    {"id": "requirements_based_testing", "category": "specification_based", "aliases": []},
    # Structure-based (white-box).
    {"id": "statement_testing", "category": "structure_based", "aliases": ["statement_coverage"]},
    {"id": "branch_testing", "category": "structure_based", "aliases": ["branch_coverage"]},
    {"id": "decision_testing", "category": "structure_based", "aliases": ["decision_coverage"]},
    {"id": "branch_condition_testing", "category": "structure_based", "aliases": []},
    {"id": "branch_condition_combination_testing", "category": "structure_based", "aliases": []},
    {"id": "mcdc_testing", "category": "structure_based", "aliases": ["mc_dc", "mcdc"]},
    {"id": "data_flow_testing", "category": "structure_based", "aliases": []},
    # Experience-based. Exploratory testing is a 29119-1 practice, kept here
    # because a test case declares it the same way.
    {"id": "error_guessing", "category": "experience_based", "aliases": []},
    {"id": "exploratory_testing", "category": "experience_based", "aliases": ["exploratory"]},
]

#: Vocabulary name -> entries, for `resolve_terms`.
TEST_VOCABULARIES: Dict[str, List[Dict[str, Any]]] = {
    "test_level": TEST_LEVELS,
    "test_kinds": TEST_KINDS,
    "techniques": TEST_TECHNIQUES,
}


# ──────────────────────────────────────────────────────────────────────────────
# Resolution
# ──────────────────────────────────────────────────────────────────────────────

def normalize_term(value: Any) -> str:
    """`"Eficiencia de desempeño"` -> `"eficiencia_de_desempeno"`."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def split_terms(value: Any) -> List[str]:
    """A YAML list or a comma-separated string, as a list of raw terms."""
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple)) else str(value).split(",")
    return [str(v).strip() for v in items if str(v).strip()]


def _characteristic_index(model: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    """(term -> characteristic id, term -> "characteristic.subcharacteristic")."""
    entries, sub_aliases, _ = QUALITY_MODELS[model]
    chars: Dict[str, str] = {}
    subs: Dict[str, str] = {}
    for e in entries:
        for term in [e["id"], *e["aliases"]]:
            chars[term] = e["id"]
        for s in e["subcharacteristics"]:
            subs[s] = f"{e['id']}.{s}"
    for old, new in sub_aliases.items():
        subs[old] = subs[new]
    return chars, subs


def resolve_quality(model: str, values: Iterable[Any]) -> Tuple[List[str], List[str]]:
    """Canonical terms of a quality model, in model order, and the unknown ones.

    A term is a characteristic (`security`), a subcharacteristic
    (`confidentiality`) or both joined by a dot (`usability.learnability`);
    aliases resolve on either side. A subcharacteristic is stored as
    `characteristic.subcharacteristic`.
    """
    chars, subs = _characteristic_index(model)
    found: List[str] = []
    unknown: List[str] = []
    for raw in values:
        head, _, tail = str(raw).partition(".")
        head_n, tail_n = normalize_term(head), normalize_term(tail)
        canonical = None
        if tail_n:
            char = chars.get(head_n)
            sub = subs.get(tail_n)
            if char and sub and sub.split(".", 1)[0] == char:
                canonical = sub
        else:
            canonical = chars.get(head_n) or subs.get(head_n)
        if canonical is None:
            unknown.append(str(raw))
        elif canonical not in found:
            found.append(canonical)
    order = _model_order(model)
    return sorted(found, key=order.index), unknown


def _model_order(model: str) -> List[str]:
    entries = QUALITY_MODELS[model][0]
    order: List[str] = []
    for e in entries:
        order.append(e["id"])
        order.extend(f"{e['id']}.{s}" for s in e["subcharacteristics"])
    return order


def characteristic_of(term: str) -> str:
    """`"security.confidentiality"` -> `"security"`."""
    return term.split(".", 1)[0]


def characteristic_ids(model: str) -> List[str]:
    """The characteristic ids of a model, in model order."""
    return [e["id"] for e in QUALITY_MODELS[model][0]]


def resolve_terms(vocabulary: str, values: Iterable[Any]) -> Tuple[List[str], List[str]]:
    """Canonical terms of a 29119 vocabulary, in vocabulary order, and the unknown ones.

    A term matches an id or an alias; `"<term>_testing"` is tried too, so
    `decision_table` resolves to `decision_table_testing`.
    """
    entries = TEST_VOCABULARIES[vocabulary]
    index: Dict[str, str] = {}
    for e in entries:
        for term in [e["id"], *e["aliases"]]:
            index[term] = e["id"]
    found: List[str] = []
    unknown: List[str] = []
    for raw in values:
        term = normalize_term(raw)
        canonical = index.get(term) or index.get(f"{term}_testing")
        if canonical is None:
            unknown.append(str(raw))
        elif canonical not in found:
            found.append(canonical)
    order = [e["id"] for e in entries]
    return sorted(found, key=order.index), unknown


def vocabulary_ids(vocabulary: str) -> List[str]:
    """The canonical ids of a 29119 vocabulary, in order."""
    return [e["id"] for e in TEST_VOCABULARIES[vocabulary]]


def technique_category(technique: str) -> Optional[str]:
    """The 29119-4 category of a canonical technique id."""
    return next((e["category"] for e in TEST_TECHNIQUES if e["id"] == technique), None)
