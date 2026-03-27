"use client";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from "recharts";

export function PerformanceCharts({
  monthlyPnl,
  byStrategy,
}: {
  monthlyPnl: Record<string, number>;
  byStrategy: Record<string, { total: number; wins: number; pnl: number }>;
}) {
  const monthlyData = Object.entries(monthlyPnl)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([month, pnl]) => ({ month: month.slice(2), pnl }));

  const strategyData = Object.entries(byStrategy).map(([name, s]) => ({
    name,
    winRate: s.total > 0 ? Math.round((s.wins / s.total) * 100) : 0,
    pnl: s.pnl,
    total: s.total,
  }));

  return (
    <div className="grid grid-cols-2 gap-6">
      {/* 월별 PnL */}
      <div className="bg-gray-900 rounded-lg p-4">
        <h3 className="text-xs text-gray-500 mb-3">월별 손익</h3>
        {monthlyData.length > 0 ? (
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={monthlyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#666" }} />
              <YAxis tick={{ fontSize: 10, fill: "#666" }} />
              <Tooltip
                contentStyle={{ background: "#1a1a2e", border: "1px solid #333", fontSize: 12 }}
                formatter={(v) => [Number(v).toLocaleString(), "손익"]}
              />
              <Bar dataKey="pnl">
                {monthlyData.map((d, i) => (
                  <Cell key={i} fill={d.pnl >= 0 ? "#ef4444" : "#3b82f6"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-gray-600 text-sm">데이터 없음</p>
        )}
      </div>

      {/* 전략별 승률 */}
      <div className="bg-gray-900 rounded-lg p-4">
        <h3 className="text-xs text-gray-500 mb-3">전략별 승률</h3>
        {strategyData.length > 0 ? (
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={strategyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#666" }} />
              <YAxis tick={{ fontSize: 10, fill: "#666" }} domain={[0, 100]} />
              <Tooltip
                contentStyle={{ background: "#1a1a2e", border: "1px solid #333", fontSize: 12 }}
                formatter={(v, name) => [
                  name === "winRate" ? `${v}%` : Number(v).toLocaleString(),
                  name === "winRate" ? "승률" : "손익",
                ]}
              />
              <Bar dataKey="winRate">
                {strategyData.map((d, i) => (
                  <Cell key={i} fill={d.winRate >= 50 ? "#ef4444" : "#3b82f6"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-gray-600 text-sm">데이터 없음</p>
        )}
      </div>
    </div>
  );
}
