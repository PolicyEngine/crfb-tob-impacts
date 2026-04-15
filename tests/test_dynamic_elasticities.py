from src.reforms import CBO_ELASTICITIES, get_option1_dynamic_dict, get_option12_dynamic_dict


def test_cbo_elasticities_use_age_based_contract():
    assert "gov.simulation.labor_supply_responses.elasticities.income.base" in CBO_ELASTICITIES
    assert (
        "gov.simulation.labor_supply_responses.elasticities.income.age_multiplier_over_threshold"
        in CBO_ELASTICITIES
    )
    assert (
        "gov.simulation.labor_supply_responses.elasticities.substitution.age_multiplier_over_threshold"
        in CBO_ELASTICITIES
    )
    assert (
        "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.secondary"
        in CBO_ELASTICITIES
    )
    assert "gov.simulation.labor_supply_responses.elasticities.income.all" not in CBO_ELASTICITIES

    for decile in (8, 9, 10):
        key = (
            "gov.simulation.labor_supply_responses.elasticities."
            f"substitution.by_position_and_decile.primary.{decile}"
        )
        assert CBO_ELASTICITIES[key]["2024-01-01.2100-12-31"] == 0.22


def test_dynamic_option_dicts_embed_age_based_elasticities():
    for dynamic_dict in (get_option1_dynamic_dict(), get_option12_dynamic_dict()):
        assert (
            dynamic_dict[
                "gov.simulation.labor_supply_responses.elasticities.income.base"
            ]["2024-01-01.2100-12-31"]
            == -0.05
        )
        assert (
            dynamic_dict[
                "gov.simulation.labor_supply_responses.elasticities.income.age_multiplier_over_threshold"
            ]["2024-01-01.2100-12-31"]
            == 2.0
        )
        assert (
            dynamic_dict[
                "gov.simulation.labor_supply_responses.elasticities.substitution.age_multiplier_over_threshold"
            ]["2024-01-01.2100-12-31"]
            == 2.0
        )
        assert (
            dynamic_dict[
                "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.secondary"
            ]["2024-01-01.2100-12-31"]
            == 0.27
        )
