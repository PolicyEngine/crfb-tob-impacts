# Wharton Budget Model Benchmark Comparison
## Option 1: Full Repeal of Social Security Benefits Taxation - Year 2054

This analysis compares PolicyEngine US estimates with the Wharton Budget Model for eliminating income taxes on Social Security benefits.

---

## Aggregate Revenue Impact

| Source | Revenue Impact (2054) |
|--------|----------------------|
| **PolicyEngine US** | **-$239.6 billion** |
| Wharton Budget Model | *(Not provided in benchmark)* |

---

## Distributional Impacts by Income Group

### Average Tax Change (2054)

| Income Group | PolicyEngine US | Wharton Budget Model | Difference | % Difference |
|--------------|-----------------|---------------------|------------|--------------|
| First quintile | -$6 | -$5 | -$1 | 20% |
| Second quintile | -$236 | -$275 | +$39 | -14% |
| Middle quintile | -$880 | -$1,730 | +$850 | -49% |
| Fourth quintile | -$1,629 | -$3,560 | +$1,931 | -54% |
| 80-90% | -$3,594 | -$4,075 | +$481 | -12% |
| 90-95% | -$6,297 | -$4,385 | -$1,912 | 44% |
| 95-99% | -$7,987 | -$4,565 | -$3,422 | 75% |
| 99-99.9% | -$4,984 | -$4,820 | -$164 | 3% |
| Top 0.1% | $0 | -$5,080 | +$5,080 | -100% |

*Negative values indicate tax cuts (benefit to taxpayers)*

### Percent Change in Income, After Taxes and Transfers (2054)

| Income Group | PolicyEngine US | Wharton Budget Model | Difference (pp) |
|--------------|-----------------|---------------------|-----------------|
| First quintile | 0.0% | 0.0% | 0.0 pp |
| Second quintile | 0.3% | 0.3% | 0.0 pp |
| Middle quintile | 0.6% | 1.3% | -0.7 pp |
| Fourth quintile | 0.8% | 1.6% | -0.8 pp |
| 80-90% | 1.2% | 1.2% | 0.0 pp |
| 90-95% | 1.5% | 0.9% | 0.6 pp |
| 95-99% | 1.4% | 0.6% | 0.8 pp |
| 99-99.9% | 0.3% | 0.2% | 0.1 pp |
| Top 0.1% | 0.0% | 0.0% | 0.0 pp |

*pp = percentage points*

---

## Key Findings

### Areas of Agreement
1. **Bottom quintiles**: Both models show minimal impact on the first quintile and similar impacts on the second quintile
2. **Upper-middle income (80-90%)**: Very similar average tax changes (~$3,600-$4,100) and identical percentage income changes (1.2%)
3. **General pattern**: Both models show the policy benefits middle-to-upper-middle income households most

### Notable Differences

1. **Middle & Fourth Quintiles**:
   - PolicyEngine shows smaller tax cuts (-$880 and -$1,629) than Wharton (-$1,730 and -$3,560)
   - This translates to smaller income changes in PolicyEngine (0.6% and 0.8%) vs Wharton (1.3% and 1.6%)

2. **High Income (90-99th percentiles)**:
   - PolicyEngine shows **larger** tax cuts for the 90-95% (-$6,297) and 95-99% (-$7,987) groups
   - Wharton shows more uniform benefits across high-income groups (-$4,385 to -$4,820)

3. **Top 0.1%**:
   - **Major discrepancy**: PolicyEngine shows $0 benefit, Wharton shows -$5,080 tax cut
   - This suggests different treatment or data for very high earners receiving Social Security benefits

---

## Methodology Notes

### PolicyEngine US (2054)
- **Dataset**: PolicyEngine US 2054 projection (`hf://policyengine/test/2054.h5`)
- **Sample**: 20,895 households (weighted: 166,973,936)
- **Scoring**: Static (no behavioral responses)
- **Reform**: Complete elimination of federal income taxation on Social Security benefits
- **Income grouping**: Based on household net income percentiles

### Wharton Budget Model (2054)
- Source: Wharton Budget Model - "Conventional Annual Distributional Effects of Eliminating Income Taxes on Social Security Benefits"
- Methodology details not provided in benchmark table

---

## Technical Implementation

### Files Generated
1. **aggregate-revenue-impact-2054**: `/data/policy_impacts_2054_wharton_summary.csv`
2. **Distributional analysis**: `/data/option1_distributional_2054.csv`
3. **Analysis scripts**:
   - `/analysis/policy-impacts-2100.ipynb` (modified for 2054 dataset)
   - `/analysis/option1_distributional_2054.py`

### Branch
All analysis conducted on the `wharton-benchmark` branch.

---

## Conclusions

1. **Overall pattern alignment**: Both models agree that eliminating SS benefit taxation primarily benefits middle-to-upper-middle income households

2. **Magnitude differences**: PolicyEngine generally shows smaller benefits to middle quintiles but larger benefits to the 90-99th percentiles

3. **Top 0.1% discrepancy**: Requires further investigation - could be due to:
   - Different assumptions about Social Security benefit receipt by very high earners
   - Different treatment of the benefit cap
   - Dataset differences in top income representation

4. **Revenue estimate**: PolicyEngine estimates -$239.6B revenue loss in 2054 (Wharton aggregate revenue not provided in benchmark)

---

*Analysis Date: October 30, 2025*
*PolicyEngine US Version: Current*
*Branch: wharton-benchmark*
