type Decision = {
  code: string;
  name: string;
  fair_gap: number;
  actual_gap: number;
  gap_residual: number;
  gap_residual_z: number;
  score: number;
  selected: boolean;
  no_trade_reasons: string[];
};

type Quote = {
  code: string;
  name: string;
  bid: number;
  ask: number;
  bid_size: number;
  ask_size: number;
  mid: number;
  spread: number;
  spread_bps: number;
  timestamp: string;
};

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function fetchJson<T>(path: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(`${apiBase}${path}`, { cache: "no-store" });
    if (!response.ok) {
      return fallback;
    }
    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

function pct(value: number) {
  return `${(value * 100).toFixed(2)}%`;
}

function won(value: number) {
  return new Intl.NumberFormat("ko-KR").format(Math.round(value));
}

export default async function Dashboard() {
  const strategy = await fetchJson<{ decisions: Decision[]; selected: Decision[] }>(
    "/strategy/today",
    { decisions: [], selected: [] }
  );
  const market = await fetchJson<{ quotes: Quote[] }>("/market/quotes", { quotes: [] });
  const selected = strategy.selected[0];

  return (
    <main>
      <header className="topbar">
        <div>
          <p>kr-quante</p>
          <h1>Korea Overnight Lead-Lag</h1>
        </div>
        <span className="mode">Live data, orders blocked</span>
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
          <span>Selected</span>
          <strong>{selected ? selected.code : "No Trade"}</strong>
          <small>{selected ? selected.name : "filters did not pass"}</small>
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Today Candidates</h2>
          <span>API: {apiBase}</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Fair Gap</th>
              <th>Actual Gap</th>
              <th>Residual</th>
              <th>Score</th>
              <th>State</th>
            </tr>
          </thead>
          <tbody>
            {strategy.decisions.map((row) => {
              const state = row.selected ? "Selected" : row.no_trade_reasons.length ? "Filtered" : "Watch";
              return (
                <tr key={row.code}>
                  <td>{row.code}</td>
                  <td>{row.name}</td>
                  <td>{pct(row.fair_gap)}</td>
                  <td>{pct(row.actual_gap)}</td>
                  <td>{pct(row.gap_residual)}</td>
                  <td>{row.score.toFixed(2)}</td>
                  <td>
                    <span className={row.selected ? "badge selected" : "badge"}>{state}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      <section className="panel market">
        <div className="section-head">
          <h2>Kiwoom Quotes</h2>
          <span>best bid/ask</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Bid</th>
              <th>Ask</th>
              <th>Spread</th>
              <th>Spread bps</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {market.quotes.map((quote) => (
              <tr key={quote.code}>
                <td>{quote.code}</td>
                <td>{quote.name}</td>
                <td>{won(quote.bid)}</td>
                <td>{won(quote.ask)}</td>
                <td>{won(quote.spread)}</td>
                <td>{quote.spread_bps.toFixed(2)}</td>
                <td>{quote.timestamp || "-"}</td>
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
