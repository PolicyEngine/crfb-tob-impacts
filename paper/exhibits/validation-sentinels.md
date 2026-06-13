The clean static release is validated against the current full-H5 production
contract. Older non-contract artifacts are not part of the release surface.

| Check | Coverage | Observed values | Interpretation |
| --- | --- | --- | --- |
| Anchor-year full-H5 coverage | fourteen reforms | 224 exact full-H5 rows | Matches the 16 anchor-year panel contract (2026, 2030, 2035-2100 by 5). |
| Late-horizon coverage | 2075, 2080, 2085, 2090, 2095, 2100 | 84 exact late-year rows | Real (no-synthetic) populace baseline datasets passing all gates. |
| Durable artifact links | exact standard rows | 100% scenario H5 URIs are R2-backed | Dashboard rows cite durable reform H5s. |
| Display interpolation boundary | non-selected annual years | 826 interpolation rows | Interpolated rows are display-only and not replacement H5s. |
