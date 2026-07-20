Labor-supply response rows are generated under the current full-H5 reform contract
and published as the dashboard's supplemental scoring surface. Each
endpoint cell saves a durable reform H5 first, computed at `2026` and `2100`
for all fourteen reforms; aggregates are then derived from those H5s using
PolicyEngine/MicroSeries operations, and intermediate annual rows are
interpolated from the endpoint ratios. The rows appear in `results.csv` under
`scoring_type = behavioral`. The current rows were rescored on 2026-07-20
with the substitution-channel fix described in the methods correction
(policyengine-us #9086 / policyengine-core #521) and carry both the income
and substitution channels; rows published 2026-06-13 through 2026-07-19 were
income-channel-only. Static scoring remains the primary surface;
labor-supply response results are partial-equilibrium estimates under the
project's age-based elasticity schedule and are not official CBO or JCT scores.
Earlier non-contract response artifacts were removed from the release surface.
