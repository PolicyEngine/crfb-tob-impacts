The clean static release is validated against the current full-H5 production
contract. Older non-contract artifacts are not part of the release surface.

| Check | Coverage | Observed values | Interpretation |
| --- | --- | --- | --- |
| Selected-year full-H5 coverage | option1-option12 | 276 exact full-H5 rows | Matches the 23-year selected panel contract. |
| Late-horizon support coverage | 2075, 2080, 2085, 2090, 2095, 2100 | 72 exact late-year rows | Uses current support-augmented baseline datasets. |
| Durable artifact links | exact standard rows | 100% scenario H5 URIs are R2-backed | Dashboard rows cite durable reform H5s. |
| Display interpolation boundary | non-selected annual years | 624 interpolation rows | Interpolated rows are display-only and not replacement H5s. |
