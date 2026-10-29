import React, { useState } from 'react'

export function RiskThresholdReference() {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="card reference-card">
      <button
        type="button"
        className="reference-toggle-btn"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <div className="reference-title">
          <span className="icon">📋</span>
          <span>Weather Hazard Thresholds &amp; Load Elevation Rules</span>
        </div>
        <span className="toggle-chevron">{isOpen ? '▲ Hide' : '▼ View Rules'}</span>
      </button>

      {isOpen && (
        <div className="reference-content">
          <p className="reference-intro">
            The backend risk scoring engine evaluates weather observations at each checkpoint along the driving corridor
            using these exact operational safety thresholds:
          </p>

          <div className="reference-table-wrapper">
            <table className="reference-table">
              <thead>
                <tr>
                  <th>Risk Category</th>
                  <th>Wind Speed</th>
                  <th>Precipitation</th>
                  <th>Snowfall</th>
                  <th>Score</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><span className="risk-tag risk-low">Low</span></td>
                  <td>&lt; 25 mph</td>
                  <td>&lt; 0.10 in/h</td>
                  <td>&lt; 0.5 in/h</td>
                  <td>10.0</td>
                </tr>
                <tr>
                  <td><span className="risk-tag risk-mod">Moderate</span></td>
                  <td>25 – 34 mph</td>
                  <td>0.10 – 0.25 in/h</td>
                  <td>0.5 – 1.0 in/h</td>
                  <td>35.0</td>
                </tr>
                <tr>
                  <td><span className="risk-tag risk-high">High</span></td>
                  <td>35 – 44 mph</td>
                  <td>&gt; 0.25 – 0.50 in/h</td>
                  <td>&gt; 1.0 – 2.0 in/h</td>
                  <td>60.0</td>
                </tr>
                <tr>
                  <td><span className="risk-tag risk-sev">Severe</span></td>
                  <td>45 – 54 mph</td>
                  <td>&gt; 0.50 – 1.00 in/h</td>
                  <td>&gt; 2.0 – 3.0 in/h</td>
                  <td>80.0</td>
                </tr>
                <tr>
                  <td><span className="risk-tag risk-notravel">No Travel</span></td>
                  <td>&ge; 55 mph</td>
                  <td>&gt; 1.00 in/h</td>
                  <td>&gt; 3.0 in/h</td>
                  <td>100.0</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="load-rules-box">
            <h4 className="rules-heading">Truck Weight Elevation Rules:</h4>
            <ul className="rules-list">
              <li><strong>Wind &ge; 55 mph</strong>: Enforces <em>No Travel</em> advisory for all load weights.</li>
              <li><strong>Wind 45 – 54 mph</strong>: Elevates to <em>No Travel</em> when truck load weight exceeds <strong>30,000 lb</strong>.</li>
              <li><strong>Wind 35 – 44 mph</strong>: Elevates to <em>Severe</em> risk when truck load weight exceeds <strong>40,000 lb</strong>.</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}
