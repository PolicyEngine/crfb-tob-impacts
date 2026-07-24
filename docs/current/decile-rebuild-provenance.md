# Legacy decile rebuild and the net-income accounting scope (H-03, H-04)

## H-03 — the phantom deciles and their root cause

The audit found material per-decile household effects for `option7` in
every year after its senior-deduction repeal expires (2029+), including
−$8.523B of summed decile change at 2100 against an exactly-zero static
revenue impact.

Root cause, measured 2026-07-23: the June production reform legs'
`household_net_income` carries **runtime drift** against any locally
computed baseline. Probing option7@2100 (a policy no-op at that year):

- June production leg vs certified-env baseline export, same no-clone
  dataset: 35,675 of 75,112 households differ (max $9,011 per
  household), weighted sum **−$8.5234B — exactly the published
  phantom**, proving the published artifact was built from this pairing.
- Certified-env leg vs the same certified-env baseline: residual only
  +$0.246B of scattered benefit-sized noise (max $1,200/household).
- Certified-env leg vs June leg directly: 1,972 households differ by up
  to $9,011 on identical policy and data — the drift is between
  runtimes, not families. The certification sentinels pin *revenue*
  reproduction; `household_net_income` includes state-tax and benefit
  components those sentinels never covered.

Per-household decile artifacts therefore require reform legs and the
baseline from the **same runtime**.

## The rebuild

All 14 legacy reforms' decile legs rescored in the certified worktree
(policyengine-us 1.700.2), run prefix `legacy_deciles_certenv_20260723`:
249 cells (18 anchor years each, minus reuse of the same-env
`option6_bracketfix_20260723` cells at 2029/2030/2032/2033 and the
`h03_roottest_20260723` option7@2100 cell), three resumable lanes
(`crfb-cert/tmp/run_legacy_decile_legs.sh`), zero failures. Datasets:
`projected_datasets_certrepro` through 2070 (byte-identical to
certinfill for shared years), the published no-clone family from 2075.
Baselines: the per-household certified-env exports
(`crfb-cert/tmp/baseline_households_{certrepro,noclone}/`), now the one
baseline every reform pairs with — `build_distributional_data.py` no
longer re-simulates a baseline at build time.

`distributional.json` rebuilt for all 16 reforms (option6 additionally
at its 2032/2033 anchors, on the bracket-capped cells). Post-rebuild
option7 phantom check: decile sums 2029-2100 are +$0.12B to +$0.31B —
same-runtime residual noise, down from −$8.5B. All 249 cell artifacts
(scenario.h5 + metadata.json) uploaded to
`r2://axiom-corpus/crfb/reform_full_h5/legacy_deciles_certenv_20260723/…`.

## H-04 — the mirror "failures" are an accounting-scope difference

The audit flagged 85 cells whose decile sums fall outside a 15% mirror
band around −revenue_impact, several with opposite sign (option5@2055:
deciles −$95B vs revenue −$5.4B). Decomposed at option5@2050 against a
true same-env no-op leg, the identity closes to the cent:

    Δ household net income  −$100.13B
      = − Δ household tax   (−$98.38B)
      + Δ benefits          (−$1.76B)
      + Δ market income     (+$0.00B)

    Δ household tax = federal revenue_impact (+$17.25B)
                    + non-federal (state) income tax (+$81.13B)

The decile metric is **all-in household net income**. For the employer
payroll swap reforms, conforming states tax the same employer
contributions the federal reform newly includes, and that state
component dwarfs the small *net* federal number (the swap's benefit-tax
repeal nearly offsets its inclusion revenue federally, but only the
federal side has the offset). The employer_ss/hi columns in results.csv
are a *decomposition* of federal revenue_impact (marginal income tax
attributable to each inclusion, credited to the trust funds per
`employer_ss_tax_income_tax_revenue`), not an addition to it.

So the mirror invariant "decile sums ≈ −federal revenue" holds only
where state/benefit knock-ons are proportionally small (the repeal and
rate-change reforms: 1-6%); for the swap family it is the wrong
identity, and the rebuilt data satisfy the correct one exactly. The
dashboard section and the artifact's `note` field now disclose the
metric's scope.
