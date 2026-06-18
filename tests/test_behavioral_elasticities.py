from src.reforms import (
    CBO_ELASTICITIES,
    get_option1_behavioral_dict,
    get_option12_behavioral_dict,
)


def test_cbo_elasticities_use_current_policyengine_us_contract():
    assert (
        "gov.simulation.labor_supply_responses.elasticities.income" in CBO_ELASTICITIES
    )
    assert (
        "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.secondary"
        in CBO_ELASTICITIES
    )
    assert (
        "gov.simulation.labor_supply_responses.elasticities.income.base"
        not in CBO_ELASTICITIES
    )
    assert (
        "gov.simulation.labor_supply_responses.elasticities.income.all"
        not in CBO_ELASTICITIES
    )
    assert (
        "gov.simulation.labor_supply_responses.elasticities.income.age_multiplier_over_threshold"
        not in CBO_ELASTICITIES
    )
    assert (
        "gov.simulation.labor_supply_responses.elasticities.substitution.age_multiplier_over_threshold"
        not in CBO_ELASTICITIES
    )

    for decile in (8, 9, 10):
        key = (
            "gov.simulation.labor_supply_responses.elasticities."
            f"substitution.by_position_and_decile.primary.{decile}"
        )
        assert CBO_ELASTICITIES[key]["2024-01-01.2100-12-31"] == 0.22


def test_behavioral_option_dicts_embed_current_policyengine_us_elasticities():
    for behavioral_dict in (
        get_option1_behavioral_dict(),
        get_option12_behavioral_dict(),
    ):
        assert (
            behavioral_dict[
                "gov.simulation.labor_supply_responses.elasticities.income"
            ]["2024-01-01.2100-12-31"]
            == -0.05
        )
        assert (
            behavioral_dict[
                "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.secondary"
            ]["2024-01-01.2100-12-31"]
            == 0.27
        )
