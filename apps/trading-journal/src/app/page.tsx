import { getMarketOverview } from "@/lib/db";
import { formatNumber, formatPercent, colorByChange } from "@/lib/format";
import Link from "next/link";

export const dynamic = "force-dynamic";

function StockTable({
  title,
  rows,
  columns,
}: {
  title: string;
  rows: Record<string, unknown>[];
  columns: { key: string; label: string; fmt?: (v: unknown) => string; color?: boolean }[];
}) {
  return (
    <div>
      <h2 className="text-sm font-semibold text-gray-400 mb-2">{title}</h2>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-gray-500 border-b border-gray-800">
            {columns.map((c) => (
              <th key={c.key} className="text-left py-1 px-2 font-normal">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-gray-900 hover:bg-gray-900/50">
              {columns.map((c) => {
                const val = row[c.key];
                const display = c.fmt
                  ? c.fmt(val)
                  : String(val ?? "-");
                const cls = c.color ? colorByChange(val as number) : "";
                return (
                  <td key={c.key} className={`py-1.5 px-2 ${cls}`}>
                    {c.key === "name" ? (
                      <Link
                        href={`/stock/${row.code}`}
                        className="hover:text-white hover:underline"
                      >
                        {display}
                      </Link>
                    ) : (
                      display
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Home() {
  const data = getMarketOverview();
  if (!data) {
    return <p className="text-gray-500">데이터 없음. 수집기를 실행하세요.</p>;
  }

  const { date, stats, topGainers, topVolume, foreignBuy } = data;

  const priceColumns = [
    { key: "name", label: "종목" },
    { key: "close", label: "현재가", fmt: (v: unknown) => formatNumber(v as number) },
    { key: "change_rate", label: "등락률", fmt: (v: unknown) => formatPercent(v as number), color: true },
    { key: "volume", label: "거래량", fmt: (v: unknown) => formatNumber(v as number) },
    { key: "mktcap", label: "시총(억)", fmt: (v: unknown) => formatNumber(v as number) },
  ];

  const foreignColumns = [
    { key: "name", label: "종목" },
    { key: "close", label: "현재가", fmt: (v: unknown) => formatNumber(v as number) },
    { key: "foreign_net_5d", label: "외인5일", fmt: (v: unknown) => formatNumber(v as number) },
    { key: "foreign_net_20d", label: "외인20일", fmt: (v: unknown) => formatNumber(v as number) },
    { key: "per", label: "PER", fmt: (v: unknown) => (v as number)?.toFixed(1) ?? "-" },
    { key: "foreign_ratio", label: "외인비율", fmt: (v: unknown) => formatPercent(v as number) },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold mb-1">시장 개요</h1>
        <p className="text-sm text-gray-500">{date}</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <div className="bg-gray-900 rounded-lg p-4">
          <p className="text-xs text-gray-500">전체 종목</p>
          <p className="text-2xl font-bold">{formatNumber(stats.total as number)}</p>
        </div>
        <div className="bg-gray-900 rounded-lg p-4">
          <p className="text-xs text-gray-500">상승</p>
          <p className="text-2xl font-bold text-red-500">{formatNumber(stats.advance as number)}</p>
        </div>
        <div className="bg-gray-900 rounded-lg p-4">
          <p className="text-xs text-gray-500">하락</p>
          <p className="text-2xl font-bold text-blue-500">{formatNumber(stats.decline as number)}</p>
        </div>
        <div className="bg-gray-900 rounded-lg p-4">
          <p className="text-xs text-gray-500">평균 등락률</p>
          <p className={`text-2xl font-bold ${colorByChange(stats.avg_change as number)}`}>
            {formatPercent(stats.avg_change as number)}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <StockTable
          title="상승률 TOP 10"
          rows={topGainers as Record<string, unknown>[]}
          columns={priceColumns}
        />
        <StockTable
          title="거래량 TOP 10"
          rows={topVolume as Record<string, unknown>[]}
          columns={priceColumns}
        />
      </div>

      <StockTable
        title="외국인 순매수 TOP 10 (5일)"
        rows={foreignBuy as Record<string, unknown>[]}
        columns={foreignColumns}
      />
    </div>
  );
}
