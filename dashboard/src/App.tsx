import { useState, useEffect } from 'react'
import { ReformSelector } from './components/ReformSelector'
import { ImpactChart } from './components/ImpactChart'
import { ComparisonTable } from './components/ComparisonTable'
import { SummaryCards } from './components/SummaryCards'
import { MethodologySection } from './components/MethodologySection'
import { loadData, calculateTotals, exportToCsv, type ScoringType } from './utils/dataLoader'
import type { YearlyImpact } from './types'
import { REFORMS } from './types'
import './App.css'

function App() {
  const [selectedReform, setSelectedReform] = useState('option1')
  const [data, setData] = useState<Record<string, YearlyImpact[]>>({})
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState<'10year' | '75year'>('10year')
  const [scoringType, setScoringType] = useState<ScoringType>('static')

  useEffect(() => {
    setLoading(true)
    loadData(scoringType)
      .then(setData)
      .finally(() => setLoading(false))
  }, [scoringType])

  const selectedData = data[selectedReform] || []
  const tenYearData = selectedData.filter(d => d.year >= 2026 && d.year <= 2035)
  const displayData = viewMode === '10year' ? tenYearData : selectedData
  const totals = calculateTotals(selectedData)
  const reform = REFORMS.find(r => r.id === selectedReform)

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner" />
        <p>Loading policy impact data...</p>
      </div>
    )
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <div className="logo-section">
            <img
              src="https://raw.githubusercontent.com/PolicyEngine/policyengine-app/master/src/images/logos/policyengine/teal.png"
              alt="PolicyEngine"
              className="logo"
            />
          </div>
          <div className="title-section">
            <h1>Social Security Taxation Reform</h1>
            <p className="subtitle">Interactive Policy Impact Dashboard</p>
          </div>
        </div>
      </header>

      <main className="main">
        <section className="intro-section">
          <p>
            This dashboard examines eight policy options for reforming the taxation of Social Security benefits,
            evaluating their budgetary impacts through 2100 using microsimulation modeling.
            Select a reform option below to explore its fiscal effects.
          </p>
        </section>

        <section className="reform-section">
          <h2>Select a Reform Option</h2>
          <ReformSelector
            selectedReform={selectedReform}
            onSelect={setSelectedReform}
          />
        </section>

        <section className="detail-section">
          <div className="reform-header">
            <h2>{reform?.name}</h2>
            <p className="reform-desc">{reform?.description}</p>
          </div>

          <SummaryCards
            tenYearTotal={totals.tenYear}
            seventyFiveYearTotal={totals.total}
          />

          <div className="scoring-toggle">
            <span className="toggle-label">Scoring Type:</span>
            <button
              className={scoringType === 'static' ? 'active' : ''}
              onClick={() => setScoringType('static')}
            >
              Static
            </button>
            <button
              className={scoringType === 'dynamic' ? 'active' : ''}
              onClick={() => setScoringType('dynamic')}
            >
              Dynamic
            </button>
          </div>

          <div className="view-toggle">
            <button
              className={viewMode === '10year' ? 'active' : ''}
              onClick={() => setViewMode('10year')}
            >
              10-Year (2026-2035)
            </button>
            <button
              className={viewMode === '75year' ? 'active' : ''}
              onClick={() => setViewMode('75year')}
            >
              75-Year (2026-2100)
            </button>
            <button
              className="export-btn"
              onClick={() => exportToCsv(selectedData, selectedReform, reform?.name || selectedReform)}
            >
              Export to CSV
            </button>
          </div>

          <div className="charts-grid">
            <ImpactChart
              data={displayData}
              title="Total Revenue Impact by Year"
            />
            <ImpactChart
              data={displayData}
              title="Trust Fund Breakdown"
              showTrustFundSplit
            />
          </div>

          <ComparisonTable
            reformId={selectedReform}
            policyEngineEstimate={Math.round(totals.tenYear)}
          />
        </section>

        <MethodologySection />
      </main>

      <footer className="footer">
        <div className="footer-content">
          <p>
            Analysis by <a href="https://policyengine.org" target="_blank" rel="noopener noreferrer">PolicyEngine</a>
            {' '}for the Committee for a Responsible Federal Budget
          </p>
          <p className="footer-note">
            Data: 2025 Social Security Trustees Report | Model: PolicyEngine US
          </p>
        </div>
      </footer>
    </div>
  )
}

export default App
