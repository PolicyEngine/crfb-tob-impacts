import React, { useState } from 'react';
import './App.css';
import PolicySelector from './components/PolicySelector';
import ImpactDisplay from './components/ImpactDisplay';
import { PolicyOption, PolicyImpact } from './types';
import { policyOptions, generatePlaceholderData } from './data/placeholderData';

function App() {
  const [selectedPolicy, setSelectedPolicy] = useState<PolicyOption | null>(null);
  const [selectedCreditValue, setSelectedCreditValue] = useState<number | null>(null);
  const [policyData, setPolicyData] = useState<PolicyImpact[] | null>(null);

  const handlePolicySelect = (policy: PolicyOption, creditValue?: number) => {
    setSelectedPolicy(policy);
    setSelectedCreditValue(creditValue || null);
    
    // Generate placeholder data for now
    const data = generatePlaceholderData(policy, creditValue);
    setPolicyData(data);
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>10-Year Budgetary Impact Analysis</h1>
        <p className="subtitle">Policy Reform Comparison Tool</p>
      </header>
      
      <main className="App-main">
        <PolicySelector 
          options={policyOptions}
          onSelect={handlePolicySelect}
          selectedPolicy={selectedPolicy}
        />
        
        {policyData && selectedPolicy && (
          <ImpactDisplay 
            data={policyData}
            policyName={selectedPolicy.name}
            creditValue={selectedCreditValue}
          />
        )}
      </main>
      
      <footer className="App-footer">
        <p>Data will be loaded from CSV file when available</p>
      </footer>
    </div>
  );
}

export default App;
