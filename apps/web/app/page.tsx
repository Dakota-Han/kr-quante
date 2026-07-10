import AutoRefresh from "./AutoRefresh";
import AutoTradePanel, { type AutoStatusPayload } from "./AutoTradePanel";
import OrderPanel from "./OrderPanel";

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

type StrategyPayload = {
  data_mode?: string;
  generated_at?: string;
  entry_window?: string;
  warnings?: string[];
  decisions: Decision[];
  selected: Decision[];
};

type HealthPayload = {
  live_enabled?: boolean;
  mode?: string;
};

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const koreanNames: Record<string, string> = {
  "069500": "KODEX 200",
  "091160": "KODEX 반도체",
  "305720": "KODEX 2차전지산업"
};

const reasonLabels: Record<string, string> = {
  "data quality check failed": "데이터 품질 확인 실패",
  "fair_gap <= 0": "해외 선행 신호 약함",
  "actual_gap >= fair_gap": "시초가에 이미 반영됨",
  "gap_residual below minimum": "남은 괴리 부족",
  "gap_residual_z below threshold": "통계적 괴리 강도 부족",
  "overseas theme signal too weak": "해외 테마 신호 약함",
  "score below threshold": "종합 점수 미달",
  "first five minute return negative": "장초반 흐름 약세",
  "price broke down after open": "시초가 이후 하락",
  "price below five minute VWAP": "5분 VWAP 하회",
  "spread wider than normal": "호가 스프레드 확대",
  "ETF premium too high": "ETF 괴리율 부담",
  "simultaneous VIX and USD/KRW stress": "VIX와 환율 동시 스트레스",
  "missing opening snapshot": "장초반 데이터 없음",
  "outside entry window": "진입 시간 아님",
  "live data warning": "데이터 경고 확인"
};

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

function displayName(code: string, fallback: string) {
  return koreanNames[code] || fallback;
}

function stateLabel(row: Decision) {
  if (row.selected) {
    return "매수 후보";
  }
  if (row.no_trade_reasons.includes("outside entry window")) {
    return "시간 외";
  }
  if (row.no_trade_reasons.includes("live data warning")) {
    return "데이터 확인";
  }
  return row.no_trade_reasons.length ? "필터 탈락" : "관찰";
}

function stateClass(row: Decision) {
  if (row.selected) {
    return "badge selected";
  }
  if (row.no_trade_reasons.includes("outside entry window")) {
    return "badge neutral";
  }
  if (row.no_trade_reasons.includes("live data warning")) {
    return "badge warning";
  }
  return row.no_trade_reasons.length ? "badge filtered" : "badge watch";
}

function primaryReason(row: Decision) {
  if (row.selected) {
    return "조건 통과";
  }
  if (row.no_trade_reasons.includes("outside entry window")) {
    return reasonLabels["outside entry window"];
  }
  if (row.no_trade_reasons.includes("live data warning")) {
    return reasonLabels["live data warning"];
  }
  const reason = row.no_trade_reasons[0];
  return reason ? reasonLabels[reason] || reason : "추가 확인";
}

function formatKiwoomTime(value: string) {
  if (!value || value.length < 6) {
    return "-";
  }
  const time = value.padStart(6, "0");
  return `${time.slice(0, 2)}:${time.slice(2, 4)}:${time.slice(4, 6)}`;
}

function dataModeLabel(mode?: string) {
  return mode === "live" ? "실제 데이터" : "샘플 데이터";
}

function formatGeneratedAt(value?: string) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  }).format(date);
}

export default async function Dashboard() {
  const strategy = await fetchJson<StrategyPayload>(
    "/strategy/today",
    { decisions: [], selected: [] }
  );
  const market = await fetchJson<{ quotes: Quote[] }>("/market/quotes", { quotes: [] });
  const health = await fetchJson<HealthPayload>("/health", {});
  const auto = await fetchJson<AutoStatusPayload>("/auto/status", {});
  const selected = strategy.selected[0];
  const warningCount = strategy.warnings?.length || 0;
  const liveTradingText = health.live_enabled ? "실주문 허용" : "실주문 차단";

  return (
    <main>
      <header className="topbar">
        <div>
          <p>kr-quante 운영 대시보드</p>
          <h1>국내 ETF 오버나이트 리드-래그</h1>
        </div>
        <div className="topbar-status">
          <span className="mode">{dataModeLabel(strategy.data_mode)} · {liveTradingText}</span>
          <AutoRefresh generatedAt={strategy.generated_at} />
        </div>
      </header>

      <section className="summary">
        <div>
          <span>전략</span>
          <strong>3 ETF v3</strong>
          <small>해외 선행 신호 + 국내 장초반 반응</small>
        </div>
        <div>
          <span>진입 시간</span>
          <strong>{strategy.entry_window || "09:06-09:12"}</strong>
          <small>지정가 주문만 허용</small>
        </div>
        <div>
          <span>청산 시간</span>
          <strong>14:50-15:10</strong>
          <small>당일 포지션 종료</small>
        </div>
        <div>
          <span>오늘 판단</span>
          <strong>{selected ? selected.code : "거래 없음"}</strong>
          <small>{selected ? displayName(selected.code, selected.name) : "필터 조건 대기"}</small>
        </div>
        <div>
          <span>데이터</span>
          <strong>{dataModeLabel(strategy.data_mode)}</strong>
          <small>{warningCount ? `경고 ${warningCount}건` : `계산 ${formatGeneratedAt(strategy.generated_at)}`}</small>
        </div>
      </section>

      <AutoTradePanel apiBase={apiBase} initialStatus={auto} />

      <OrderPanel apiBase={apiBase} liveEnabled={Boolean(health.live_enabled)} />

      <section className="panel candidates">
        <div className="section-head">
          <h2>오늘 매매 후보</h2>
          <span>API: {apiBase}</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>종목코드</th>
                <th>종목명</th>
                <th className="number optional">예상 괴리</th>
                <th className="number optional">시초 괴리</th>
                <th className="number">남은 괴리</th>
                <th className="number">점수</th>
                <th>판단</th>
                <th>주요 사유</th>
              </tr>
            </thead>
            <tbody>
              {strategy.decisions.length ? (
                strategy.decisions.map((row) => (
                  <tr key={row.code}>
                    <td>{row.code}</td>
                    <td>{displayName(row.code, row.name)}</td>
                    <td className="number optional">{pct(row.fair_gap)}</td>
                    <td className="number optional">{pct(row.actual_gap)}</td>
                    <td className="number">{pct(row.gap_residual)}</td>
                    <td className="number">{row.score.toFixed(2)}</td>
                    <td>
                      <span className={stateClass(row)}>{stateLabel(row)}</span>
                    </td>
                    <td>{primaryReason(row)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8}>전략 데이터를 불러오지 못했습니다.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel market">
        <div className="section-head">
          <h2>키움 실시간 호가</h2>
          <span>최우선 매수·매도 호가</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>종목코드</th>
                <th>종목명</th>
                <th className="number">매수호가</th>
                <th className="number">매도호가</th>
                <th className="number">스프레드</th>
                <th className="number optional">스프레드(bp)</th>
                <th className="optional">시간</th>
              </tr>
            </thead>
            <tbody>
              {market.quotes.length ? (
                market.quotes.map((quote) => (
                  <tr key={quote.code}>
                    <td>{quote.code}</td>
                    <td>{displayName(quote.code, quote.name)}</td>
                    <td className="number">{won(quote.bid)}</td>
                    <td className="number">{won(quote.ask)}</td>
                    <td className="number">{won(quote.spread)}</td>
                    <td className="number optional">{quote.spread_bps.toFixed(2)}</td>
                    <td className="optional">{formatKiwoomTime(quote.timestamp)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7}>키움 시세를 불러오지 못했습니다.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid">
        <div className="panel">
          <h2>거래 안 하는 조건</h2>
          <ul>
            <li>시초가가 이미 예상 상승분을 대부분 반영하면 진입하지 않음</li>
            <li>09:00-09:05 흐름이 음수면 장초반 매수세 부족으로 판단</li>
            <li>호가 스프레드와 ETF 괴리율이 평소보다 크면 제외</li>
            <li>VIX와 원/달러가 동시에 스트레스 구간이면 신규 진입 중단</li>
          </ul>
        </div>
        <div className="panel">
          <h2>주문 안전장치</h2>
          <ul>
            <li>시장가 주문은 차단</li>
            <li>사용자 승인 없이는 실주문 불가</li>
            <li>09:12까지 미체결이면 주문 취소</li>
            <li>놓친 체결을 따라가서 추격 매수하지 않음</li>
          </ul>
        </div>
      </section>
    </main>
  );
}
