import { PolicyOption, PolicyImpact } from '../types';

export const policyOptions: PolicyOption[] = [
  {
    id: 1,
    name: "Repeal Social Security Benefits Tax",
    description: "Expand earned income tax credit for low and middle-income families"
  },
  {
    id: 2,
    name: "Flat Social Security Tax",
    description: "Increase federal spending on infrastructure modernization projects"
  },
  {
    id: 3,
    name: "Flat Social Security Tax with Bonus Senior Deduction Extension",
    description: "Implement comprehensive healthcare system reforms and subsidies"
  },
  {
    id: 4,
    name: "Social Security Credit",
    description: "Variable Social Security Credit with multiple value options",
    hasMultipleCreditValues: true,
    creditValues: [300, 600, 900, 1200, 1500]
  },
  {
    id: 5,
    name: "Roth Style Swap",
    description: "Increase federal education grants and student loan forgiveness"
  },
  {
    id: 6,
    name: "Roth Style Swap with Phase-In",
    description: "Tax incentives for renewable energy and climate initiatives"
  }
];

export const generatePlaceholderData = (policy: PolicyOption, creditValue?: number): PolicyImpact[] => {
  const data: PolicyImpact[] = [];
  
  // Generate realistic-looking placeholder data based on policy type
  for (let year = 1; year <= 10; year++) {
    let impact: number;
    
    switch (policy.id) {
      case 1: // Repeal Social Security Benefits Tax
        impact = -120 - (year * 5) + Math.random() * 20 - 10;
        break;
      case 2: // Infrastructure
        impact = -200 - (year * 10) + Math.random() * 30 - 15;
        break;
      case 3: // Healthcare
        impact = -300 + (year * 15) + Math.random() * 40 - 20;
        break;
      case 4: // Social Security Credit (varies by credit value)
        const baseImpact = creditValue ? -(creditValue / 10) : -90;
        impact = baseImpact - (year * 8) + Math.random() * 25 - 12.5;
        break;
      case 5: // Education
        impact = -150 - (year * 3) + Math.random() * 20 - 10;
        break;
      case 6: // Green Energy
        impact = -80 + (year * 5) + Math.random() * 15 - 7.5;
        break;
      default:
        impact = -100 + Math.random() * 50 - 25;
    }
    
    data.push({
      year,
      impact: Math.round(impact * 10) / 10 // Round to 1 decimal place
    });
  }
  
  return data;
};