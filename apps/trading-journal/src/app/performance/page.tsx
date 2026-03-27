import { getTradeStats } from "@/lib/db";
import { formatNumber, colorByChange } from "@/lib/format";
import { PerformanceCharts } from "./charts";

export const dynamic = "force-dynamic";

export default function PerformancePage() {
  const stats = getTradeStats();

  if (!stats || stats.totalTrades === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">성과 분석</h1>
        <p className="text-gray-500">
          매매 기록이 없습니다. 매매일지에서 기록을 추가하세요.
        </p>
      </div>
    );
  }

  const sortedStocks = Object.entries(stats.byStock)
    .sort(([, a], [, b]) => b.pnl - a.pnl);

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">성과 분석</h1>

      {/* 요약 카드 */}
      <div className="grid grid-cols-5 gap-4">
        <StatCard label="총 매매" value={String(stats.totalTrades)} />
        <StatCard label="매도/손절" value={String(stats.totalSells)} />
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
        <StatCard
          label="평균 손익"
          value={formatNumber(stats.avgPnl)}
          color={colorByChange(stats.avgPnl)}
        />
      </div>

      {/* 차트 */}
      <PerformanceCharts
        monthlyPnl={stats.monthlyPnl}
        byStrategy={stats.byStrategy}
      />

      {/* 전략별 성과 */}
      <div>
        <h2 className="text-sm font-semibold text-gray-400 mb-2">전략별 성과</h2>
        <div className="grid grid-cols-3 gap-4">
          {Object.entries(stats.byStrategy).map(([strategy, s]) => (
            <div key={strategy} className="bg-gray-900 rounded-lg p-4">
              <p className="text-xs text-gray-500 mb-1">{strategy}</p>
              <div className="flex justify-between items-baseline">
                <span className="text-lg font-bold">
                  {s.total > 0 ? `${((s.wins / s.total) * 100).toFixed(0)}%` : "-"}
                </span>
                <span className={`text-sm ${colorByChange(s.pnl)}`}>
                  {formatNumber(s.pnl)}
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-1">{s.total}건</p>
            </div>
          ))}
        </div>
      </div>

      {/* 종목별 성과 */}
      <div>
        <h2 className="text-sm font-semibold text-gray-400 mb-2">종목별 성과</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-500 border-b border-gray-800">
              <th className="text-left py-2 px-2">종목</th>
              <th className="text-right py-2 px-2">매매 수</th>
              <th className="text-right py-2 px-2">승률</th>
              <th className="text-right py-2 px-2">총 손익</th>
            </tr>
          </thead>
          <tbody>
            {sortedStocks.map(([code, s]) => (
              <tr key={code} className="border-b border-gray-900">
                <td className="py-1.5 px-2">
                  {s.name}
                  <span className="text-xs text-gray-600 ml-1">{code}</span>
                </td>
                <td className="py-1.5 px-2 text-right">{s.trades}</td>
                <td className="py-1.5 px-2 text-right">
                  {s.trades > 0 ? `${((s.wins / s.trades) * 100).toFixed(0)}%` : "-"}
                </td>
                <td className={`py-1.5 px-2 text-right ${colorByChange(s.pnl)}`}>
                  {formatNumber(s.pnl)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
