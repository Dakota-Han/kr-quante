"use client";

import { useMemo, useState } from "react";

type AutoEvent = {
  id: string;
  ts: string;
  trading_day: string;
  type: string;
  level: string;
  message: string;
  code?: string | null;
  side?: string | null;
  quantity?: number | null;
  limit_price?: number | null;
  budget_krw?: number | null;
  estimated_pnl_krw?: number | null;
};

export type AutoStatusPayload = {
  settings?: {
    enabled?: boolean;
    daily_budget_krw?: number;
    buy_window?: string;
    sell_window?: string;
  };
  state?: {
    active_position?: {
      code: string;
      name?: string;
      quantity: number;
      entry_limit_price: number;
      exit_limit_price?: number;
      estimated_pnl_krw?: number;
      fill_status?: string;
    } | null;
    last_tick_at?: string;
    last_status?: string;
  };
  events?: AutoEvent[];
  summary?: {
    estimated_realized_pnl_krw?: number;
    event_count?: number;
  };
  runtime?: {
    live_enabled?: boolean;
    mode?: string;
    buy_window?: string;
    sell_window?: string;
  };
};

type AutoTradePanelProps = {
  apiBase: string;
  initialStatus: AutoStatusPayload;
};

const eventLabels: Record<string, string> = {
  settings_updated: "설정 변경",
  no_candidate: "후보 없음",
  budget_too_small: "예산 부족",
  buy_blocked: "매수 차단",
  buy_submitted: "매수 주문",
  no_position: "보유 없음",
  sell_blocked: "매도 차단",
  sell_submitted: "매도 주문",
  manual_tick: "수동 점검",
  error: "오류"
};

const statusLabels: Record<string, string> = {
  idle: "대기",
  disabled: "꺼짐",
  waiting: "시간 대기",
  no_candidate: "후보 없음",
  budget_too_small: "예산 부족",
  buy_blocked: "매수 차단",
  buy_submitted: "매수 주문 제출",
  buy_already_submitted: "매수 완료",
  no_position: "보유 없음",
  sell_blocked: "매도 차단",
  sell_submitted: "매도 주문 제출",
  sell_already_submitted: "청산 주문 완료",
  error: "오류"
};

function formatWon(value?: number | null) {
  if (value === undefined || value === null) {
    return "-";
  }
  return `${new Intl.NumberFormat("ko-KR").format(Math.round(value))}원`;
}

function formatTime(value?: string) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  }).format(date);
}

function eventLabel(type: string) {
  return eventLabels[type] || type;
}

function statusLabel(type?: string) {
  return type ? statusLabels[type] || type : "-";
}

export default function AutoTradePanel({ apiBase, initialStatus }: AutoTradePanelProps) {
  const [status, setStatus] = useState<AutoStatusPayload>(initialStatus || {});
  const [dailyBudget, setDailyBudget] = useState(String(initialStatus?.settings?.daily_budget_krw ?? 10000));
  const [enabled, setEnabled] = useState(Boolean(initialStatus?.settings?.enabled));
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");

  const activePosition = status.state?.active_position;
  const liveEnabled = Boolean(status.runtime?.live_enabled);
  const modeText = useMemo(() => {
    if (!enabled) {
      return "자동매매 꺼짐";
    }
    if (!liveEnabled) {
      return "자동매매 켜짐 · 실주문 차단";
    }
    return "자동매매 켜짐 · 실주문 가능";
  }, [enabled, liveEnabled]);

  async function refreshStatus() {
    const response = await fetch(`${apiBase}/auto/status`, { cache: "no-store" });
    const next = (await response.json()) as AutoStatusPayload;
    setStatus(next);
    setEnabled(Boolean(next.settings?.enabled));
    setDailyBudget(String(next.settings?.daily_budget_krw ?? 10000));
  }

  async function saveSettings(nextEnabled = enabled) {
    setLoading(true);
    setNotice("");
    try {
      const response = await fetch(`${apiBase}/auto/settings`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          enabled: nextEnabled,
          daily_budget_krw: Number(dailyBudget || 0)
        })
      });
      const next = (await response.json()) as AutoStatusPayload;
      setStatus(next);
      setEnabled(Boolean(next.settings?.enabled));
      setDailyBudget(String(next.settings?.daily_budget_krw ?? 10000));
      setNotice("자동매매 설정을 저장했습니다.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "설정 저장 실패");
    } finally {
      setLoading(false);
    }
  }

  async function toggleEnabled() {
    const nextEnabled = !enabled;
    setEnabled(nextEnabled);
    await saveSettings(nextEnabled);
  }

  async function runTick() {
    setLoading(true);
    setNotice("");
    try {
      const response = await fetch(`${apiBase}/auto/tick`, { method: "POST" });
      const result = await response.json();
      await refreshStatus();
      setNotice(result.reason || result.status || "자동매매 점검 완료");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "자동 점검 실패");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel auto-panel">
      <div className="section-head">
        <h2>자동매매</h2>
        <span>{modeText}</span>
      </div>

      <div className="auto-grid">
        <div className="auto-card">
          <span>상태</span>
          <strong>{statusLabel(status.state?.last_status)}</strong>
          <small>최근 점검 {formatTime(status.state?.last_tick_at)}</small>
        </div>
        <div className="auto-card">
          <span>하루 최대 주문금액</span>
          <strong>{formatWon(Number(dailyBudget || 0))}</strong>
          <small>1주 가격보다 작으면 자동 주문 안 함</small>
        </div>
        <div className="auto-card">
          <span>자동 시간</span>
          <strong>{status.runtime?.buy_window || "09:06-09:12"}</strong>
          <small>청산 {status.runtime?.sell_window || "14:50-15:10"}</small>
        </div>
        <div className="auto-card">
          <span>주문 기준 손익</span>
          <strong>{formatWon(status.summary?.estimated_realized_pnl_krw || 0)}</strong>
          <small>체결 확정 전에는 추정값</small>
        </div>
      </div>

      <div className="trade-grid auto-settings">
        <label>
          <span>하루 최대 금액</span>
          <input value={dailyBudget} onChange={(event) => setDailyBudget(event.target.value)} inputMode="numeric" />
        </label>
        <label>
          <span>자동매매</span>
          <button type="button" className={enabled ? "danger" : ""} onClick={toggleEnabled} disabled={loading}>
            {enabled ? "자동매매 끄기" : "자동매매 켜기"}
          </button>
        </label>
        <label>
          <span>설정</span>
          <button type="button" onClick={() => saveSettings()} disabled={loading}>
            금액 저장
          </button>
        </label>
      </div>

      <div className="trade-actions">
        <button type="button" onClick={runTick} disabled={loading}>
          지금 1회 점검
        </button>
      </div>

      {notice && (
        <div className="trade-result muted-result">
          <span>{notice}</span>
        </div>
      )}

      {activePosition && (
        <div className="trade-result">
          <strong>
            자동 보유 {activePosition.code} {activePosition.quantity}주
          </strong>
          <span>진입 지정가 {formatWon(activePosition.entry_limit_price)}</span>
          {activePosition.exit_limit_price ? <span>청산 지정가 {formatWon(activePosition.exit_limit_price)}</span> : null}
          <span>상태 {activePosition.fill_status || "submitted_unconfirmed"}</span>
          <small>주문 응답 기준입니다. 체결 확정은 키움 체결조회 연동 후 보강됩니다.</small>
        </div>
      )}

      <div className="log-table">
        <div className="section-head">
          <h3>자동매매 로그</h3>
          <span>최근 {status.events?.length || 0}건</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>시간</th>
                <th>구분</th>
                <th>종목</th>
                <th className="number">수량</th>
                <th className="number">가격</th>
                <th className="number optional">손익</th>
                <th>내용</th>
              </tr>
            </thead>
            <tbody>
              {status.events?.length ? (
                status.events.slice(0, 20).map((event) => (
                  <tr key={event.id}>
                    <td>{formatTime(event.ts)}</td>
                    <td>
                      <span className={event.level === "error" ? "badge warning" : "badge neutral"}>
                        {eventLabel(event.type)}
                      </span>
                    </td>
                    <td>{event.code || "-"}</td>
                    <td className="number">{event.quantity ?? "-"}</td>
                    <td className="number">{formatWon(event.limit_price)}</td>
                    <td className="number optional">{formatWon(event.estimated_pnl_krw)}</td>
                    <td>{event.message}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7}>아직 자동매매 로그가 없습니다.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
