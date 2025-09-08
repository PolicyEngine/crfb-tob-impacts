import React from 'react';
import { PolicyImpact } from '../types';
import html2canvas from 'html2canvas';
import './ImpactDisplay.css';

interface ImpactDisplayProps {
  data: PolicyImpact[];
  policyName: string;
  creditValue?: number | null;
}

const ImpactDisplay: React.FC<ImpactDisplayProps> = ({ data, policyName, creditValue }) => {
  const handleSaveChart = async () => {
    const chartElement = document.querySelector('.impact-chart') as HTMLElement;
    if (chartElement) {
      try {
        const canvas = await html2canvas(chartElement, {
          backgroundColor: '#f8f9fa',
          scale: 2,
        });
        
        const link = document.createElement('a');
        link.download = `${policyName.replace(/\s+/g, '_')}_impact_chart.png`;
        link.href = canvas.toDataURL();
        link.click();
      } catch (error) {
        console.error('Error saving chart:', error);
      }
    }
  };

  const formatCurrency = (value: number, includeSign: boolean = true): string => {
    const absValue = Math.abs(value);
    const sign = value < 0 ? '-' : (includeSign ? '+' : '');
    
    if (absValue >= 1000) {
      return `${sign}$${(absValue / 1000).toFixed(1)}T`;
    } else {
      return `${sign}$${absValue.toFixed(0)}B`;
    }
  };

  const totalImpact = data.reduce((sum, item) => sum + item.impact, 0);
  
  // Calculate max impact for scaling
  const maxImpact = Math.max(...data.map(d => Math.abs(d.impact)));
  
  // Determine appropriate rounding based on the scale of values
  let yAxisMax: number;
  let tickInterval: number;
  
  if (maxImpact <= 50) {
    yAxisMax = Math.ceil(maxImpact / 10) * 10;
    tickInterval = 20;
  } else if (maxImpact <= 100) {
    yAxisMax = Math.ceil(maxImpact / 20) * 20;
    tickInterval = 40;
  } else if (maxImpact <= 200) {
    yAxisMax = Math.ceil(maxImpact / 40) * 40;
    tickInterval = 40;
  } else {
    yAxisMax = Math.ceil(maxImpact / 50) * 50;
    tickInterval = 50;
  }
  
  const chartHeight = 200; // Height for each half (positive and negative)
  
  // Generate y-axis tick values for symmetric display
  const yAxisTicks: number[] = [];
  for (let i = yAxisMax; i >= -yAxisMax; i -= tickInterval) {
    yAxisTicks.push(i);
  }
  
  // Ensure 0 is included
  if (!yAxisTicks.includes(0)) {
    yAxisTicks.push(0);
    yAxisTicks.sort((a, b) => b - a);
  }

  return (
    <div className="impact-display">
      <div className="impact-header">
        <h2>Budgetary Impact: {policyName}</h2>
        {creditValue && <p className="credit-value">Credit Value: ${creditValue}</p>}
        <div className="total-impact">
          <span>10-Year Total Impact:</span>
          <span className={`impact-value ${totalImpact < 0 ? 'negative' : 'positive'}`}>
            {formatCurrency(totalImpact, false)}
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
              {item.year}
            </div>
            <div className={`table-cell impact-cell ${item.impact < 0 ? 'negative' : 'positive'}`}>
              {formatCurrency(item.impact, false)}
            </div>
          </div>
        ))}
      </div>

      <div className="impact-chart">
        <div className="chart-header">
          <h3>Impact of {policyName}{creditValue ? ` ($${creditValue})` : ''}</h3>
          <button className="save-chart-button" onClick={handleSaveChart}>
            Save Chart
          </button>
        </div>
        <img src="/policyengine.png" alt="PolicyEngine" className="chart-logo" />
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
                      {formatCurrency(item.impact, false)}
                    </span>
                    <div 
                      className={`bar ${isNegative ? 'negative' : 'positive'}`}
                      style={{ 
                        height: `${barHeight}px`,
                        [isNegative ? 'top' : 'bottom']: `${chartHeight}px`
                      }}
                      title={`Year ${item.year}: ${formatCurrency(item.impact)}`}
                    />
                    <span className="bar-label">{item.year}</span>
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