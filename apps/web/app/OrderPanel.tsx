"use client";

import { useMemo, useState } from "react";

type OrderPanelProps = {
  apiBase: string;
  liveEnabled: boolean;
};

type PreviewResponse = {
  status: "preview" | "no_trade";
  reason?: string;
  warnings?: string[];
  preview?: {
    code: string;
    side: string;
    quantity: number;
    limit_price: number;
    position_weight: number;
    max_loss_pct: number;
    stop_pct: number;
    client_order_id: string;
    reason: string;
  };
  decision?: {
    code: string;
    name: string;
    score: number;
    gap_residual: number;
  };
};

type SubmitResponse = {
  status?: string;
  detail?: string;
  kiwoom?: Record<string, unknown>;
};

function formatWon(value: number) {
  return new Intl.NumberFormat("ko-KR").format(Math.round(value));
}

function formatPct(value: number) {
  return `${(value * 100).toFixed(2)}%`;
}

export default function OrderPanel({ apiBase, liveEnabled }: OrderPanelProps) {
  const [accountEquity, setAccountEquity] = useState("10000000");
  const [stopPct, setStopPct] = useState("1.0");
  const [approvedBy, setApprovedBy] = useState("");
  const [sellCode, setSellCode] = useState("091160");
  const [sellQuantity, setSellQuantity] = useState("");
  const [sellLimitPrice, setSellLimitPrice] = useState("");
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [submitResult, setSubmitResult] = useState<SubmitResponse | null>(null);
  const [sellResult, setSellResult] = useState<SubmitResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const canSubmit = useMemo(() => {
    return Boolean(preview?.preview && approvedBy.trim());
  }, [approvedBy, preview]);

  async function requestPreview() {
    setLoading(true);
    setSubmitResult(null);
    try {
      const response = await fetch(`${apiBase}/orders/preview`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          account_equity: Number(accountEquity || 0),
          raw_stop_pct: Number(stopPct || 0) / 100
        })
      });
      setPreview((await response.json()) as PreviewResponse);
    } catch (error) {
      setPreview({ status: "no_trade", reason: error instanceof Error ? error.message : "preview failed" });
    } finally {
      setLoading(false);
    }
  }

  async function submitOrder() {
    if (!preview?.preview) {
      return;
    }
    setLoading(true);
    setSubmitResult(null);
    try {
      const response = await fetch(`${apiBase}/orders/submit`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          preview: preview.preview,
          approved_by: approvedBy.trim(),
          order_type: "LMT"
        })
      });
      setSubmitResult((await response.json()) as SubmitResponse);
    } catch (error) {
      setSubmitResult({ detail: error instanceof Error ? error.message : "submit failed" });
    } finally {
      setLoading(false);
    }
  }

  async function submitSellOrder() {
    setLoading(true);
    setSellResult(null);
    try {
      const response = await fetch(`${apiBase}/orders/sell-limit`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          code: sellCode.trim(),
          quantity: Number(sellQuantity || 0),
          limit_price: Number(sellLimitPrice || 0),
          approved_by: approvedBy.trim()
        })
      });
      setSellResult((await response.json()) as SubmitResponse);
    } catch (error) {
      setSellResult({ detail: error instanceof Error ? error.message : "sell failed" });
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel trade-panel">
      <div className="section-head">
        <h2>실전 주문</h2>
        <span>{liveEnabled ? "실주문 허용" : "실주문 차단"}</span>
      </div>

      <div className="trade-grid">
        <label>
          <span>계좌 기준 금액</span>
          <input value={accountEquity} onChange={(event) => setAccountEquity(event.target.value)} inputMode="numeric" />
        </label>
        <label>
          <span>손절 기준</span>
          <input value={stopPct} onChange={(event) => setStopPct(event.target.value)} inputMode="decimal" />
        </label>
        <label>
          <span>승인자</span>
          <input value={approvedBy} onChange={(event) => setApprovedBy(event.target.value)} placeholder="이름 입력" />
        </label>
      </div>

      <div className="trade-actions">
        <button type="button" onClick={requestPreview} disabled={loading}>
          주문 미리보기
        </button>
        <button type="button" className="danger" onClick={submitOrder} disabled={loading || !canSubmit}>
          승인 후 지정가 매수
        </button>
      </div>

      {preview?.status === "no_trade" && (
        <div className="trade-result muted-result">
          <strong>주문 없음</strong>
          <span>{preview.reason || "현재 조건에서는 주문 후보가 없습니다."}</span>
          {preview.warnings?.length ? <small>데이터 경고 {preview.warnings.length}건</small> : null}
        </div>
      )}

      {preview?.preview && (
        <div className="trade-result">
          <strong>
            {preview.preview.code} {preview.preview.side} {preview.preview.quantity}주
          </strong>
          <span>지정가 {formatWon(preview.preview.limit_price)}원</span>
          <span>비중 {formatPct(preview.preview.position_weight)} · 손절 {formatPct(preview.preview.stop_pct)}</span>
          <span>최대 손실 예산 {formatPct(preview.preview.max_loss_pct)}</span>
          <small>{preview.preview.client_order_id}</small>
        </div>
      )}

      {submitResult && (
        <div className={submitResult.status === "submitted" ? "trade-result" : "trade-result muted-result"}>
          <strong>{submitResult.status === "submitted" ? "주문 요청 완료" : "주문 차단"}</strong>
          <span>{submitResult.detail || JSON.stringify(submitResult.kiwoom || submitResult)}</span>
        </div>
      )}

      <div className="close-box">
        <h3>수동 청산</h3>
        <div className="trade-grid">
          <label>
            <span>종목코드</span>
            <input value={sellCode} onChange={(event) => setSellCode(event.target.value)} />
          </label>
          <label>
            <span>매도 수량</span>
            <input value={sellQuantity} onChange={(event) => setSellQuantity(event.target.value)} inputMode="numeric" />
          </label>
          <label>
            <span>매도 지정가</span>
            <input value={sellLimitPrice} onChange={(event) => setSellLimitPrice(event.target.value)} inputMode="numeric" />
          </label>
        </div>
        <div className="trade-actions">
          <button
            type="button"
            className="danger"
            onClick={submitSellOrder}
            disabled={loading || !approvedBy.trim() || !sellCode.trim() || !sellQuantity || !sellLimitPrice}
          >
            승인 후 지정가 매도
          </button>
        </div>
        {sellResult && (
          <div className={sellResult.status === "submitted" ? "trade-result" : "trade-result muted-result"}>
            <strong>{sellResult.status === "submitted" ? "매도 요청 완료" : "매도 차단"}</strong>
            <span>{sellResult.detail || JSON.stringify(sellResult.kiwoom || sellResult)}</span>
          </div>
        )}
      </div>
    </section>
  );
}
