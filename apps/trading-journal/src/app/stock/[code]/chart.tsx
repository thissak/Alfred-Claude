"use client";

import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

interface PriceRow {
  date: string;
  close: number;
  volume: number;
}

export function PriceChartWrapper({ prices }: { prices: PriceRow[] }) {
  const data = prices.map((p) => ({
    date: p.date.slice(5), // MM-DD
    close: p.close,
    volume: p.volume,
  }));

  return (
    <div className="bg-gray-900 rounded-lg p-4">
      <h2 className="text-xs text-gray-500 mb-3">가격 차트</h2>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#666" }} />
          <YAxis
            yAxisId="price"
            orientation="right"
            tick={{ fontSize: 10, fill: "#666" }}
            domain={["auto", "auto"]}
          />
          <YAxis yAxisId="vol" orientation="left" tick={false} />
          <Tooltip
            contentStyle={{ background: "#1a1a2e", border: "1px solid #333", fontSize: 12 }}
            labelStyle={{ color: "#999" }}
          />
          <Bar yAxisId="vol" dataKey="volume" fill="#333" opacity={0.5} />
          <Line
            yAxisId="price"
            type="monotone"
            dataKey="close"
            stroke="#3b82f6"
            dot={false}
            strokeWidth={2}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
