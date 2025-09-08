import React, { useState, useEffect } from 'react';
import './App.css';
import PolicySelector from './components/PolicySelector';
import ImpactDisplay from './components/ImpactDisplay';
import { PolicyOption, PolicyImpact } from './types';
import { loadCSVData, processCSVData } from './utils/csvLoader';

function App() {
  const [selectedPolicy, setSelectedPolicy] = useState<PolicyOption | null>(null);
  const [selectedCreditValue, setSelectedCreditValue] = useState<number | null>(null);
  const [policyData, setPolicyData] = useState<PolicyImpact[] | null>(null);
  const [policies, setPolicies] = useState<PolicyOption[]>([]);
  const [allImpactData, setAllImpactData] = useState<Map<string, PolicyImpact[]>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const csvData = await loadCSVData('/policy_impacts.csv');
        const { policies: loadedPolicies, impactData } = processCSVData(csvData);
        setPolicies(loadedPolicies);
        setAllImpactData(impactData);
        setLoading(false);
      } catch (err) {
        console.error('Error loading CSV data:', err);
        setError('Failed to load policy data');
        setLoading(false);
      }
    };
    
    loadData();
  }, []);

  const handlePolicySelect = (policy: PolicyOption, creditValue?: number) => {
    setSelectedPolicy(policy);
    setSelectedCreditValue(creditValue || null);
    
    // Get data from loaded CSV
    const key = creditValue ? `${policy.id}_${creditValue}` : `${policy.id}`;
    const data = allImpactData.get(key);
    
    if (data) {
      setPolicyData(data);
    } else {
      setPolicyData(null);
    }
  };

  if (loading) {
    return (
      <div className="App">
        <header className="App-header">
          <h1>Social Security Taxation of Benefits</h1>
          <p className="subtitle">Loading policy data...</p>
        </header>
      </div>
    );
  }

  if (error) {
    return (
      <div className="App">
        <header className="App-header">
          <h1>Social Security Taxation of Benefits</h1>
          <p className="subtitle" style={{ color: '#e74c3c' }}>{error}</p>
        </header>
      </div>
    );
  }

  return (
    <div className="App">
      <header className="App-header">
        <h1>Social Security Taxation of Benefits</h1>
        <p className="subtitle">10-Year Budgetary Impact Analysis</p>
      </header>
      
      <main className="App-main">
        <PolicySelector 
          options={policies}
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
        <p>Data loaded from policy_impacts.csv</p>
        <button 
          className="download-button"
          onClick={() => {
            const link = document.createElement('a');
            link.href = '/policy_impacts.csv';
            link.download = 'policy_impacts.csv';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
          }}
        >
          Download CSV Data
        </button>
        <img src="/policyengine.png" alt="PolicyEngine" className="footer-logo" />
      </footer>
    </div>
  );
}

export default App;
