import { getTradeStats } from "@/lib/db";
import { formatNumber, colorByChange } from "@/lib/format";
import { PsychologyCharts } from "./charts";

export const dynamic = "force-dynamic";

const EMOTION_LABELS: Record<string, string> = {
  confident: "확신",
  calm: "침착",
  fomo: "FOMO",
  fearful: "불안",
  impulsive: "충동",
  unknown: "미분류",
};

export default function PsychologyPage() {
  const stats = getTradeStats();

  if (!stats || stats.totalTrades === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">심리 분석</h1>
        <p className="text-gray-500">
          매매 기록이 없습니다. 매매일지에서 기록을 추가하세요.
        </p>
      </div>
    );
  }

  const emotionEntries = Object.entries(stats.emotionPnl)
    .sort(([, a], [, b]) => b.total - a.total);

  // 감정별 매매 기록 타임라인
  const emotionTimeline = stats.allTrades
    .filter((t) => t.side !== "buy")
    .map((t) => ({
      date: t.traded_at,
      emotion: t.emotion ?? "unknown",
      emotionLabel: EMOTION_LABELS[t.emotion ?? "unknown"] ?? t.emotion,
      name: t.name,
      pnl: t.pnl ?? 0,
      side: t.side,
    }));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">심리 분석</h1>
        <p className="text-sm text-gray-500 mt-1">
          매매 시 감정이 수익에 어떤 영향을 미치는지 분석합니다
        </p>
      </div>

      {/* 핵심 인사이트 */}
      {emotionEntries.length > 1 && (
        <div className="bg-gray-900 rounded-lg p-4 border border-gray-800">
          <h2 className="text-sm font-semibold text-gray-400 mb-2">핵심 인사이트</h2>
          <div className="space-y-1 text-sm">
            {(() => {
              const best = emotionEntries.reduce((a, b) =>
                (b[1].total >= 2 && b[1].pnl / b[1].total > a[1].pnl / a[1].total) ? b : a
              );
              const worst = emotionEntries.reduce((a, b) =>
                (b[1].total >= 2 && b[1].pnl / b[1].total < a[1].pnl / a[1].total) ? b : a
              );
              return (
                <>
                  <p>
                    <span className="text-red-400">최고 성과 감정:</span>{" "}
                    {EMOTION_LABELS[best[0]] ?? best[0]} — 평균{" "}
                    <span className={colorByChange(best[1].avgPnl)}>
                      {formatNumber(best[1].avgPnl)}원
                    </span>
                    /건 ({best[1].total}건)
                  </p>
                  <p>
                    <span className="text-blue-400">최저 성과 감정:</span>{" "}
                    {EMOTION_LABELS[worst[0]] ?? worst[0]} — 평균{" "}
                    <span className={colorByChange(worst[1].avgPnl)}>
                      {formatNumber(worst[1].avgPnl)}원
                    </span>
                    /건 ({worst[1].total}건)
                  </p>
                </>
              );
            })()}
          </div>
        </div>
      )}

      {/* 차트 */}
      <PsychologyCharts
        emotionPnl={Object.fromEntries(
          emotionEntries.map(([k, v]) => [EMOTION_LABELS[k] ?? k, v])
        )}
      />

      {/* 감정별 상세 */}
      <div>
        <h2 className="text-sm font-semibold text-gray-400 mb-2">감정별 상세</h2>
        <div className="grid grid-cols-3 gap-4">
          {emotionEntries.map(([emotion, s]) => {
            const winRate = s.total > 0 ? (s.wins / s.total) * 100 : 0;
            return (
              <div key={emotion} className="bg-gray-900 rounded-lg p-4">
                <div className="flex justify-between items-start mb-2">
                  <span className="text-sm font-medium">
                    {EMOTION_LABELS[emotion] ?? emotion}
                  </span>
                  <span className="text-xs text-gray-500">{s.total}건</span>
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">승률</span>
                    <span className={winRate >= 50 ? "text-red-500" : "text-blue-500"}>
                      {winRate.toFixed(0)}%
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">총 손익</span>
                    <span className={colorByChange(s.pnl)}>{formatNumber(s.pnl)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">평균 손익</span>
                    <span className={colorByChange(s.avgPnl)}>{formatNumber(s.avgPnl)}</span>
                  </div>
                  {/* 승률 바 */}
                  <div className="w-full bg-gray-800 rounded-full h-1.5 mt-2">
                    <div
                      className={`h-1.5 rounded-full ${winRate >= 50 ? "bg-red-500" : "bg-blue-500"}`}
                      style={{ width: `${Math.min(winRate, 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 최근 매도 타임라인 */}
      {emotionTimeline.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-400 mb-2">매도 타임라인 (감정 추적)</h2>
          <div className="space-y-1">
            {emotionTimeline.slice(0, 30).map((t, i) => (
              <div
                key={i}
                className="flex items-center gap-3 text-sm py-1.5 border-b border-gray-900"
              >
                <span className="text-gray-500 w-20">{t.date}</span>
                <span className="w-20">{t.name}</span>
                <span
                  className={`px-1.5 py-0.5 rounded text-xs ${
                    t.side === "cut"
                      ? "bg-yellow-900/50 text-yellow-400"
                      : "bg-blue-900/50 text-blue-400"
                  }`}
                >
                  {t.side === "cut" ? "손절" : "매도"}
                </span>
                <span className="px-1.5 py-0.5 rounded text-xs bg-gray-800 text-gray-400">
                  {t.emotionLabel}
                </span>
                <span className={`ml-auto ${colorByChange(t.pnl)}`}>
                  {formatNumber(t.pnl)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
