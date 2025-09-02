import Papa from 'papaparse';
import { PolicyOption, PolicyImpact } from '../types';

export interface CSVRow {
  policy_id: string;
  policy_name: string;
  credit_value: string;
  year: string;
  impact_billions: string;
}

export const loadCSVData = async (url: string): Promise<CSVRow[]> => {
  return new Promise((resolve, reject) => {
    Papa.parse(url, {
      download: true,
      header: true,
      complete: (results) => {
        resolve(results.data as CSVRow[]);
      },
      error: (error) => {
        reject(error);
      }
    });
  });
};

export const processCSVData = (data: CSVRow[]): {
  policies: PolicyOption[];
  impactData: Map<string, PolicyImpact[]>;
} => {
  const policies: PolicyOption[] = [];
  const impactData = new Map<string, PolicyImpact[]>();
  const policyMap = new Map<number, PolicyOption>();

  // Process data
  data.forEach((row) => {
    if (!row.policy_id || !row.year || !row.impact_billions) return;
    
    const policyId = parseInt(row.policy_id);
    const year = parseInt(row.year);
    const impact = parseFloat(row.impact_billions);
    const creditValue = row.credit_value ? parseInt(row.credit_value) : null;
    
    // Create policy option if not exists
    if (!policyMap.has(policyId)) {
      const policy: PolicyOption = {
        id: policyId,
        name: row.policy_name,
        description: getPolicyDescription(policyId),
        hasMultipleCreditValues: policyId === 4,
        creditValues: policyId === 4 ? [300, 600, 900, 1200, 1500] : undefined
      };
      policyMap.set(policyId, policy);
      policies.push(policy);
    }
    
    // Create key for impact data
    const key = creditValue ? `${policyId}_${creditValue}` : `${policyId}`;
    
    // Add impact data
    if (!impactData.has(key)) {
      impactData.set(key, []);
    }
    
    impactData.get(key)!.push({
      year: year - 2024, // Convert to relative year (1-10)
      impact: impact
    });
  });

  // Sort policies by ID
  policies.sort((a, b) => a.id - b.id);
  
  // Sort impact data by year
  impactData.forEach((impacts) => {
    impacts.sort((a, b) => a.year - b.year);
  });

  return { policies, impactData };
};

const getPolicyDescription = (id: number): string => {
  const descriptions: { [key: number]: string } = {
    1: "Expand earned income tax credit for low and middle-income families",
    2: "Increase federal spending on infrastructure modernization projects",
    3: "Implement comprehensive healthcare system reforms and subsidies",
    4: "Variable child tax credit with multiple value options",
    5: "Increase federal education grants and student loan forgiveness",
    6: "Tax incentives for renewable energy and climate initiatives"
  };
  return descriptions[id] || "Policy reform option";
};