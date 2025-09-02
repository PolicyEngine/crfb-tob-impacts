import React from 'react';
import { PolicyImpact } from '../types';
import './ImpactDisplay.css';

interface ImpactDisplayProps {
  data: PolicyImpact[];
  policyName: string;
  creditValue?: number | null;
}

const ImpactDisplay: React.FC<ImpactDisplayProps> = ({ data, policyName, creditValue }) => {
  const formatCurrency = (value: number): string => {
    const absValue = Math.abs(value);
    const sign = value < 0 ? '-' : '+';
    
    if (absValue >= 1000) {
      return `${sign}$${(absValue / 1000).toFixed(1)}T`;
    } else {
      return `${sign}$${absValue.toFixed(0)}B`;
    }
  };

  const totalImpact = data.reduce((sum, item) => sum + item.impact, 0);
  const currentYear = new Date().getFullYear();
  
  // Calculate max impact for scaling
  const maxImpact = Math.max(...data.map(d => Math.abs(d.impact)));
  const yAxisMax = Math.ceil(maxImpact / 50) * 50; // Round up to nearest 50
  const chartHeight = 200; // Height for each half (positive and negative)
  
  // Generate y-axis tick values (5 ticks including 0)
  const tickInterval = yAxisMax / 2;
  const yAxisTicks = [yAxisMax, tickInterval, 0, -tickInterval, -yAxisMax];

  return (
    <div className="impact-display">
      <div className="impact-header">
        <h2>Budgetary Impact: {policyName}</h2>
        {creditValue && <p className="credit-value">Credit Value: ${creditValue}</p>}
        <div className="total-impact">
          <span>10-Year Total Impact:</span>
          <span className={`impact-value ${totalImpact < 0 ? 'negative' : 'positive'}`}>
            {formatCurrency(totalImpact)}
          </span>
        </div>
      </div>

      <div className="impact-table">
        <div className="table-header">
          <div className="table-cell">Fiscal Year</div>
          <div className="table-cell">Impact</div>
        </div>
        {data.map((item) => (
          <div key={item.year} className="table-row">
            <div className="table-cell year-cell">
              {currentYear + item.year - 1}
            </div>
            <div className={`table-cell impact-cell ${item.impact < 0 ? 'negative' : 'positive'}`}>
              {formatCurrency(item.impact)}
            </div>
          </div>
        ))}
      </div>

      <div className="impact-chart">
        <h3>Impact Over Time</h3>
        <div className="chart-container">
          <div className="y-axis">
            {yAxisTicks.map((tick) => (
              <div key={tick} className="y-axis-tick">
                <span className="tick-label">
                  {tick === 0 ? '$0' : tick > 0 ? `$${tick}B` : `-$${Math.abs(tick)}B`}
                </span>
                <div className={`tick-line ${tick === 0 ? 'zero-line' : ''}`}></div>
              </div>
            ))}
          </div>
          <div className="bar-chart-wrapper">
            <div className="zero-line-absolute"></div>
            <div className="bar-chart">
              {data.map((item) => {
                const barHeight = (Math.abs(item.impact) / yAxisMax) * chartHeight;
                const isNegative = item.impact < 0;
                
                return (
                  <div key={item.year} className="bar-container">
                    <span 
                      className="bar-value"
                      style={{
                        top: isNegative ? 
                          `${chartHeight + barHeight + 5}px` : 
                          `${chartHeight - barHeight - 20}px`
                      }}
                    >
                      {formatCurrency(item.impact).replace('+', '')}
                    </span>
                    <div 
                      className={`bar ${isNegative ? 'negative' : 'positive'}`}
                      style={{ 
                        height: `${barHeight}px`,
                        [isNegative ? 'top' : 'bottom']: `${chartHeight}px`
                      }}
                      title={`Year ${item.year}: ${formatCurrency(item.impact)}`}
                    />
                    <span className="bar-label">Y{item.year}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ImpactDisplay;