export interface PolicyOption {
  id: number;
  name: string;
  description: string;
  hasMultipleCreditValues?: boolean;
  creditValues?: number[];
}

export interface PolicyImpact {
  year: number;
  impact: number;
}