import React, { useState } from 'react';
import { PolicyOption } from '../types';
import './PolicySelector.css';

interface PolicySelectorProps {
  options: PolicyOption[];
  onSelect: (policy: PolicyOption, creditValue?: number) => void;
  selectedPolicy: PolicyOption | null;
}

const PolicySelector: React.FC<PolicySelectorProps> = ({ options, onSelect, selectedPolicy }) => {
  const [selectedCreditValue, setSelectedCreditValue] = useState<number>(900);

  const handlePolicyClick = (policy: PolicyOption) => {
    if (policy.hasMultipleCreditValues) {
      onSelect(policy, selectedCreditValue);
    } else {
      onSelect(policy);
    }
  };

  const handleCreditValueChange = (value: number) => {
    setSelectedCreditValue(value);
    if (selectedPolicy && selectedPolicy.hasMultipleCreditValues) {
      onSelect(selectedPolicy, value);
    }
  };

  return (
    <div className="policy-selector">
      <h2>Select a Policy Reform</h2>
      <div className="policy-grid">
        {options.map((option) => (
          <div
            key={option.id}
            className={`policy-card ${selectedPolicy?.id === option.id ? 'selected' : ''}`}
            onClick={() => handlePolicyClick(option)}
          >
            <h3>Option {option.id}</h3>
            <p>{option.name}</p>
            <span className="policy-description">{option.description}</span>
          </div>
        ))}
      </div>

      {selectedPolicy && selectedPolicy.hasMultipleCreditValues && (
        <div className="credit-selector">
          <h3>Select Credit Value for {selectedPolicy.name}</h3>
          <div className="credit-buttons">
            {selectedPolicy.creditValues?.map((value) => (
              <button
                key={value}
                className={`credit-button ${selectedCreditValue === value ? 'selected' : ''}`}
                onClick={() => handleCreditValueChange(value)}
              >
                ${value}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default PolicySelector;