"""Property tests for how scorers read and compose a dataset's assumptions.

Invariants (each holds for every input the strategies draw):

1. Fail closed: reading an economic assumption record either raises or
   returns a contract that pins one reform. An active contract names a
   module:attribute path and a module hash and came from a record whose
   ``active`` is exactly ``True``; an inactive one names nothing and came from
   a record that names no reform.
2. Order and agreement: the scoring reform is the economic assumption reform
   (when the dataset records one) followed by the tax assumption reform (when
   it is active that year), and a policy composed after it keeps that prefix,
   so baseline and reform carry the same assumptions.
3. No assumption, no change: without an economic assumption the scoring
   reform is the very object the tax-assumption-only loader returns.
4. Identity: a recorded hash equal to the module's loads; any other hash
   raises, naming both.
5. compose_reforms keeps the non-None reforms in order and returns a lone
   reform unwrapped.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("hypothesis")

from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from src import tax_assumption_loader as loader  # noqa: E402
from tests import scoring_fakes as sf  # noqa: E402
from tests.pipeline_fakes import (  # noqa: E402
    FakeEconomicReform,
    FakeTaxReform,
    flatten_reform,
)
from tests.scoring_fakes import FakePolicyReform  # noqa: E402

SPEC_PATTERN = re.compile(r"^[^:]+:.+$")
MISSING = object()

record_values = {
    "active": st.sampled_from([True, False, None, "true", 1, 0, MISSING]),
    "reform": st.sampled_from(
        [None, "", "pkg.mod", "pkg.mod:", ":attr", "pkg.mod:attr", 5, MISSING]
    ),
    "applies_before": st.sampled_from(["tax_assumption", "policy", None, MISSING]),
    "module_sha256": st.sampled_from([None, "", "abc123", MISSING]),
}


@st.composite
def economic_records(draw):
    record = {}
    for key, values in record_values.items():
        value = draw(values)
        if value is not MISSING:
            record[key] = value
    return record


@settings(max_examples=400, deadline=None)
@given(record=economic_records())
def test_economic_records_fail_closed(record):
    try:
        contract = loader.economic_assumption_contract_from_metadata(
            {"economic_assumption": record}
        )
    except ValueError:
        return
    if contract.active:
        assert record.get("active") is True
        assert SPEC_PATTERN.match(contract.reform)
        assert contract.module_sha256
        assert record.get("applies_before", "tax_assumption") == "tax_assumption"
    else:
        assert record == {} or record.get("active", False) is False
        assert record.get("reform") is None
        assert contract.reform is None and contract.module_sha256 is None


tax_names = st.sampled_from(
    [
        None,
        "",
        loader.CURRENT_LAW_LITERAL_ASSUMPTION,
        loader.TRUSTEES_2025_CORE_THRESHOLDS_ASSUMPTION,
        loader.LEGACY_TRUSTEES_CORE_THRESHOLDS_ASSUMPTION,
    ]
)


@settings(max_examples=300, deadline=None)
@given(
    year=st.integers(2026, 2105),
    name=tax_names,
    start=st.integers(2030, 2040),
    end=st.integers(2090, 2105),
    economic=st.sampled_from(["active", "inactive", "missing"]),
)
def test_scoring_reform_is_economic_then_tax_and_policy_keeps_the_prefix(
    year, name, start, end, economic
):
    metadata = {"tax_assumption": {"name": name, "start_year": start, "end_year": end}}
    if economic == "active":
        metadata["economic_assumption"] = sf.economic_record()
    elif economic == "inactive":
        metadata["economic_assumption"] = dict(sf.INACTIVE_RECORD)

    with pytest.MonkeyPatch.context() as patch:
        sf.patch_tax_reform(patch)
        scoring = loader.load_scoring_assumption_reform_for_metadata(metadata, year)
        tax_active = (
            name in loader.SUPPORTED_TAX_ASSUMPTION_NAMES and start <= year <= end
        )
        expected = (FakeEconomicReform,) * (economic == "active") + (
            FakeTaxReform,
        ) * tax_active
        assert flatten_reform(scoring) == expected

        scored = flatten_reform(loader.compose_reforms(scoring, FakePolicyReform))
        assert scored == (*expected, FakePolicyReform)

        if economic != "active":
            assert scoring is loader.load_tax_assumption_reform_for_metadata(
                metadata, year
            )


@settings(max_examples=60, deadline=None)
@given(
    comment=st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126), max_size=40
    ),
    recorded=st.one_of(
        st.none(), st.text(alphabet="0123456789abcdef", min_size=64, max_size=64)
    ),
)
def test_only_the_recorded_module_hash_loads(tmp_path_factory, comment, recorded):
    directory = tmp_path_factory.mktemp("assumption")
    module = Path(directory) / "property_assumption_module.py"
    module.write_text(
        "from policyengine_core.reforms import Reform\n"
        f"# {comment}\n"
        "class trustees(Reform):\n"
        "    pass\n"
    )
    actual = hashlib.sha256(module.read_bytes()).hexdigest()
    recorded = actual if recorded is None else recorded
    metadata = {
        "economic_assumption": {
            "active": True,
            "reform": "property_assumption_module:trustees",
            "module_sha256": recorded,
        }
    }
    sys.path.insert(0, str(directory))
    sys.modules.pop("property_assumption_module", None)
    try:
        if recorded == actual:
            reform = loader.load_economic_assumption_reform_for_metadata(metadata)
            assert reform.__name__ == "trustees"
        else:
            with pytest.raises(ValueError) as error:
                loader.load_economic_assumption_reform_for_metadata(metadata)
            assert recorded in str(error.value) and actual in str(error.value)
    finally:
        sys.path.remove(str(directory))
        sys.modules.pop("property_assumption_module", None)


reform_items = st.sampled_from(
    [None, FakeEconomicReform, FakeTaxReform, FakePolicyReform, "dict-reform"]
)


@settings(max_examples=300, deadline=None)
@given(reforms=st.lists(reform_items, max_size=6))
def test_compose_reforms_keeps_non_none_reforms_in_order(reforms):
    composed = loader.compose_reforms(*reforms)
    kept = [reform for reform in reforms if reform is not None]
    if not kept:
        assert composed is None
    elif len(kept) == 1:
        assert composed is kept[0]
    else:
        assert composed == tuple(kept)
