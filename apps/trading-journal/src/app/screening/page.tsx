import { getScreening, getLatestDate } from "@/lib/db";
import { formatNumber, formatPercent, colorByChange } from "@/lib/format";
import Link from "next/link";

export const dynamic = "force-dynamic";

const PRESETS: Record<string, { label: string; filters: Record<string, [string, number | number[]]>; sort: string }> = {
  value: {
    label: "저평가",
    filters: { per: ["between", [1, 10]], pbr: ["<", 1.5] },
    sort: "mktcap",
  },
  momentum: {
    label: "모멘텀",
    filters: { return_5d: [">", 5], volume_ratio_5d: [">", 2] },
    sort: "return_5d",
  },
  foreign: {
    label: "외국인 매집",
    filters: { foreign_net_5d: [">", 0], foreign_net_20d: [">", 0] },
    sort: "foreign_net_20d",
  },
  largecap: {
    label: "대형주",
    filters: { mktcap: [">", 50000] },
    sort: "mktcap",
  },
};

export default async function ScreeningPage({
  searchParams,
}: {
  searchParams: Promise<{ preset?: string }>;
}) {
  const { preset: presetKey } = await searchParams;
  const preset = PRESETS[presetKey ?? "value"] ?? PRESETS.value;
  const date = getLatestDate();
  const results = getScreening(date, preset.filters, preset.sort, 50);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold mb-2">종목 스크리닝</h1>
        <p className="text-sm text-gray-500">{date}</p>
      </div>

      <div className="flex gap-2">
        {Object.entries(PRESETS).map(([key, p]) => (
          <Link
            key={key}
            href={`/screening?preset=${key}`}
            className={`px-3 py-1.5 rounded text-sm ${
              (presetKey ?? "value") === key
                ? "bg-white text-black"
                : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            {p.label}
          </Link>
        ))}
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="text-gray-500 border-b border-gray-800">
            <th className="text-left py-2 px-2">#</th>
            <th className="text-left py-2 px-2">종목</th>
            <th className="text-right py-2 px-2">현재가</th>
            <th className="text-right py-2 px-2">등락률</th>
            <th className="text-right py-2 px-2">시총(억)</th>
            <th className="text-right py-2 px-2">PER</th>
            <th className="text-right py-2 px-2">PBR</th>
            <th className="text-right py-2 px-2">외인비율</th>
            <th className="text-right py-2 px-2">외인5일</th>
            <th className="text-right py-2 px-2">MA20</th>
            <th className="text-right py-2 px-2">5일수익</th>
            <th className="text-right py-2 px-2">거래량비</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => (
            <tr key={r.code} className="border-b border-gray-900 hover:bg-gray-900/50">
              <td className="py-1.5 px-2 text-gray-500">{i + 1}</td>
              <td className="py-1.5 px-2">
                <Link href={`/stock/${r.code}`} className="hover:text-white hover:underline">
                  {r.name}
                </Link>
                <span className="text-xs text-gray-600 ml-1">{r.code}</span>
              </td>
              <td className="py-1.5 px-2 text-right">{formatNumber(r.close)}</td>
              <td className={`py-1.5 px-2 text-right ${colorByChange(r.return_1d)}`}>
                {formatPercent(r.return_1d)}
              </td>
              <td className="py-1.5 px-2 text-right">{formatNumber(r.mktcap)}</td>
              <td className="py-1.5 px-2 text-right">{r.per?.toFixed(1) ?? "-"}</td>
              <td className="py-1.5 px-2 text-right">{r.pbr?.toFixed(2) ?? "-"}</td>
              <td className="py-1.5 px-2 text-right">{r.foreign_ratio?.toFixed(1) ?? "-"}%</td>
              <td className={`py-1.5 px-2 text-right ${colorByChange(r.foreign_net_5d)}`}>
                {formatNumber(r.foreign_net_5d)}
              </td>
              <td className="py-1.5 px-2 text-right">{formatNumber(Math.round(r.ma20 ?? 0))}</td>
              <td className={`py-1.5 px-2 text-right ${colorByChange(r.return_5d)}`}>
                {formatPercent(r.return_5d)}
              </td>
              <td className="py-1.5 px-2 text-right">{r.volume_ratio_5d?.toFixed(1) ?? "-"}x</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
