const decisions = [
  {
    code: "069500",
    name: "KODEX 200",
    fairGap: "0.55%",
    actualGap: "0.32%",
    score: "0.82",
    state: "Watch"
  },
  {
    code: "091160",
    name: "KODEX 반도체",
    fairGap: "1.28%",
    actualGap: "0.66%",
    score: "1.74",
    state: "Selected"
  },
  {
    code: "305720",
    name: "KODEX 2차전지산업",
    fairGap: "0.81%",
    actualGap: "0.31%",
    score: "0.94",
    state: "Filtered"
  }
];

export default function Dashboard() {
  return (
    <main>
      <header className="topbar">
        <div>
          <p>kr-quante</p>
          <h1>Korea Overnight Lead-Lag</h1>
        </div>
        <span className="mode">Mock mode</span>
      </header>

      <section className="summary">
        <div>
          <span>Strategy</span>
          <strong>3 ETF v3</strong>
          <small>Only one trade per day</small>
        </div>
        <div>
          <span>Entry</span>
          <strong>09:06-09:12</strong>
          <small>Limit order only</small>
        </div>
        <div>
          <span>Exit</span>
          <strong>14:50-15:10</strong>
          <small>Flat by close</small>
        </div>
        <div>
          <span>Risk</span>
          <strong>0.30%</strong>
          <small>Per-trade loss budget</small>
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Today Candidates</h2>
          <span>sample data</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Fair Gap</th>
              <th>Actual Gap</th>
              <th>Score</th>
              <th>State</th>
            </tr>
          </thead>
          <tbody>
            {decisions.map((row) => (
              <tr key={row.code}>
                <td>{row.code}</td>
                <td>{row.name}</td>
                <td>{row.fairGap}</td>
                <td>{row.actualGap}</td>
                <td>{row.score}</td>
                <td>
                  <span className={row.state === "Selected" ? "badge selected" : "badge"}>{row.state}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="grid">
        <div className="panel">
          <h2>No Trade Filters</h2>
          <ul>
            <li>actual_gap must be below fair_gap</li>
            <li>09:00-09:05 return must be non-negative</li>
            <li>spread and ETF premium must be normal</li>
            <li>VIX and USD/KRW stress cannot happen together</li>
          </ul>
        </div>
        <div className="panel">
          <h2>Order Policy</h2>
          <ul>
            <li>Market orders are blocked</li>
            <li>Manual approval is required</li>
            <li>Unfilled entries are cancelled by 09:12</li>
            <li>No chasing after a missed fill</li>
          </ul>
        </div>
      </section>
    </main>
  );
}
