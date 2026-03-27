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
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from "recharts";

interface EmotionStats {
  total: number;
  wins: number;
  pnl: number;
  avgPnl: number;
}

export function PsychologyCharts({
  emotionPnl,
}: {
  emotionPnl: Record<string, EmotionStats>;
}) {
  const barData = Object.entries(emotionPnl).map(([name, s]) => ({
    name,
    avgPnl: s.avgPnl,
    winRate: s.total > 0 ? Math.round((s.wins / s.total) * 100) : 0,
    total: s.total,
  }));

  const radarData = Object.entries(emotionPnl).map(([name, s]) => ({
    emotion: name,
    winRate: s.total > 0 ? Math.round((s.wins / s.total) * 100) : 0,
    count: s.total,
  }));

  return (
    <div className="grid grid-cols-2 gap-6">
      {/* 감정별 평균 손익 */}
      <div className="bg-gray-900 rounded-lg p-4">
        <h3 className="text-xs text-gray-500 mb-3">감정별 평균 손익</h3>
        {barData.length > 0 ? (
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={barData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#999" }} />
              <YAxis tick={{ fontSize: 10, fill: "#666" }} />
              <Tooltip
                contentStyle={{ background: "#1a1a2e", border: "1px solid #333", fontSize: 12 }}
                formatter={(v, name) => [
                  name === "avgPnl" ? `${Number(v).toLocaleString()}원` : `${v}%`,
                  name === "avgPnl" ? "평균 손익" : "승률",
                ]}
              />
              <Bar dataKey="avgPnl">
                {barData.map((d, i) => (
                  <Cell key={i} fill={d.avgPnl >= 0 ? "#ef4444" : "#3b82f6"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-gray-600 text-sm">데이터 없음</p>
        )}
      </div>

      {/* 감정 레이더 */}
      <div className="bg-gray-900 rounded-lg p-4">
        <h3 className="text-xs text-gray-500 mb-3">감정별 승률 레이더</h3>
        {radarData.length >= 3 ? (
          <ResponsiveContainer width="100%" height={250}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="#333" />
              <PolarAngleAxis dataKey="emotion" tick={{ fontSize: 11, fill: "#999" }} />
              <PolarRadiusAxis tick={{ fontSize: 9, fill: "#666" }} domain={[0, 100]} />
              <Radar
                dataKey="winRate"
                stroke="#ef4444"
                fill="#ef4444"
                fillOpacity={0.2}
              />
            </RadarChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-[250px]">
            <p className="text-gray-600 text-sm">3개 이상 감정 데이터 필요</p>
          </div>
        )}
      </div>
    </div>
  );
}
