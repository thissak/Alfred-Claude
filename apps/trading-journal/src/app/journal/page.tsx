import { getTrades, getTradeStats } from "@/lib/db";
import { formatNumber, formatPercent, colorByChange } from "@/lib/format";
import { TradeForm } from "./form";

export const dynamic = "force-dynamic";

export default function JournalPage() {
  const trades = getTrades();
  const stats = getTradeStats();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">매매일지</h1>

      {stats && stats.totalTrades > 0 && (
        <div className="grid grid-cols-4 gap-4">
          <StatCard label="총 매매" value={String(stats.totalTrades)} />
          <StatCard
            label="승률"
            value={`${stats.winRate.toFixed(0)}%`}
            color={stats.winRate >= 50 ? "text-red-500" : "text-blue-500"}
          />
          <StatCard
            label="총 손익"
            value={formatNumber(stats.totalPnl)}
            color={colorByChange(stats.totalPnl)}
          />
          <div className="bg-gray-900 rounded-lg p-4">
            <p className="text-xs text-gray-500 mb-1">감정별 승률</p>
            <div className="space-y-0.5 text-xs">
              {Object.entries(stats.byEmotion).map(([em, s]) => (
                <div key={em} className="flex justify-between">
                  <span className="text-gray-400">{em}</span>
                  <span>{s.total > 0 ? `${((s.wins / s.total) * 100).toFixed(0)}% (${s.total}건)` : "-"}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <TradeForm />

      {trades.length === 0 ? (
        <p className="text-gray-500">매매 기록이 없습니다. 위 폼에서 첫 매매를 기록하세요.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-500 border-b border-gray-800">
              <th className="text-left py-2 px-2">날짜</th>
              <th className="text-left py-2 px-2">종목</th>
              <th className="text-left py-2 px-2">매매</th>
              <th className="text-right py-2 px-2">수량</th>
              <th className="text-right py-2 px-2">가격</th>
              <th className="text-right py-2 px-2">금액</th>
              <th className="text-left py-2 px-2">전략</th>
              <th className="text-left py-2 px-2">감정</th>
              <th className="text-right py-2 px-2">손익</th>
              <th className="text-left py-2 px-2">사유</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t) => (
              <tr key={t.id} className="border-b border-gray-900 hover:bg-gray-900/50">
                <td className="py-1.5 px-2 text-gray-400">{t.traded_at}</td>
                <td className="py-1.5 px-2">{t.name}</td>
                <td className="py-1.5 px-2">
                  <span
                    className={`px-1.5 py-0.5 rounded text-xs ${
                      t.side === "buy"
                        ? "bg-red-900/50 text-red-400"
                        : t.side === "cut"
                        ? "bg-yellow-900/50 text-yellow-400"
                        : "bg-blue-900/50 text-blue-400"
                    }`}
                  >
                    {t.side === "buy" ? "매수" : t.side === "cut" ? "손절" : "매도"}
                  </span>
                </td>
                <td className="py-1.5 px-2 text-right">{formatNumber(t.qty)}</td>
                <td className="py-1.5 px-2 text-right">{formatNumber(t.price)}</td>
                <td className="py-1.5 px-2 text-right">{formatNumber(t.total_amount)}</td>
                <td className="py-1.5 px-2">
                  {t.strategy && (
                    <span className="text-xs text-gray-400 bg-gray-800 px-1.5 py-0.5 rounded">
                      {t.strategy}
                    </span>
                  )}
                </td>
                <td className="py-1.5 px-2">
                  {t.emotion && (
                    <span className="text-xs text-gray-400 bg-gray-800 px-1.5 py-0.5 rounded">
                      {t.emotion}
                    </span>
                  )}
                </td>
                <td className={`py-1.5 px-2 text-right ${colorByChange(t.pnl)}`}>
                  {t.pnl != null ? formatNumber(t.pnl) : "-"}
                </td>
                <td className="py-1.5 px-2 text-gray-400 text-xs max-w-40 truncate">
                  {t.reason ?? ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-gray-900 rounded-lg p-4">
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-2xl font-bold ${color ?? ""}`}>{value}</p>
    </div>
  );
}
