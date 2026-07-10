"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, useTransition } from "react";

const NORMAL_REFRESH_MS = 5000;
const ENTRY_REFRESH_MS = 3000;

function kstSecondOfDay(date: Date) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Seoul",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  }).formatToParts(date);
  const hour = Number(parts.find((part) => part.type === "hour")?.value || "0");
  const minute = Number(parts.find((part) => part.type === "minute")?.value || "0");
  const second = Number(parts.find((part) => part.type === "second")?.value || "0");
  return hour * 3600 + minute * 60 + second;
}

function currentRefreshMs() {
  const now = kstSecondOfDay(new Date());
  const entryStart = 9 * 3600 + 6 * 60;
  const entryEnd = 9 * 3600 + 12 * 60;
  return now >= entryStart && now <= entryEnd ? ENTRY_REFRESH_MS : NORMAL_REFRESH_MS;
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
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  }).format(date);
}

type AutoRefreshProps = {
  generatedAt?: string;
};

export default function AutoRefresh({ generatedAt }: AutoRefreshProps) {
  const router = useRouter();
  const [intervalMs, setIntervalMs] = useState(NORMAL_REFRESH_MS);
  const [isVisible, setIsVisible] = useState(true);
  const [isPending, startTransition] = useTransition();

  const refresh = useCallback(() => {
    setIntervalMs(currentRefreshMs());
    startTransition(() => {
      router.refresh();
    });
  }, [router]);

  useEffect(() => {
    setIntervalMs(currentRefreshMs());
  }, [generatedAt]);

  useEffect(() => {
    const onVisibilityChange = () => {
      const visible = document.visibilityState === "visible";
      setIsVisible(visible);
      if (visible) {
        refresh();
      }
    };

    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("focus", refresh);
    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("focus", refresh);
    };
  }, [refresh]);

  useEffect(() => {
    if (!isVisible) {
      return undefined;
    }
    const timer = window.setInterval(refresh, intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs, isVisible, refresh]);

  return (
    <div className="refresh-status" aria-live="polite">
      <span className={isPending ? "refresh-dot pending" : "refresh-dot"} />
      <span>{isVisible ? `자동 ${intervalMs / 1000}초` : "일시정지"}</span>
      <span>갱신 {formatTime(generatedAt)}</span>
      <button type="button" className="refresh-button" onClick={refresh} disabled={isPending}>
        새로고침
      </button>
    </div>
  );
}
