import { getStockDetail } from "@/lib/db";
import { formatNumber, formatPercent, colorByChange } from "@/lib/format";
import { PriceChartWrapper } from "./chart";

export const dynamic = "force-dynamic";

export default async function StockPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  const { security, prices, latestVal, flow, screening } = getStockDetail(code);

  if (!security) {
    return <p className="text-gray-500">종목을 찾을 수 없습니다: {code}</p>;
  }

  const latest = prices[prices.length - 1];
  const scr = screening as Record<string, unknown> | undefined;
  const val = latestVal as Record<string, unknown> | undefined;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">
          {security.name}
          <span className="text-sm text-gray-500 ml-2">{code} · {security.market}</span>
        </h1>
        {latest && (
          <div className="flex items-baseline gap-3 mt-1">
            <span className="text-3xl font-bold">{formatNumber(latest.close)}</span>
            <span className={`text-lg ${colorByChange(latest.change_rate)}`}>
              {formatPercent(latest.change_rate)}
            </span>
          </div>
        )}
      </div>

      {prices.length > 0 && <PriceChartWrapper prices={prices} />}

      <div className="grid grid-cols-3 gap-4">
        <InfoCard title="밸류에이션">
          <InfoRow label="PER" value={val?.per != null ? (val.per as number).toFixed(1) : "-"} />
          <InfoRow label="PBR" value={val?.pbr != null ? (val.pbr as number).toFixed(2) : "-"} />
          <InfoRow label="EPS" value={formatNumber(val?.eps as number)} />
          <InfoRow label="시총(억)" value={formatNumber(latest?.mktcap)} />
          <InfoRow label="외인비율" value={val?.foreign_ratio != null ? `${(val.foreign_ratio as number).toFixed(1)}%` : "-"} />
        </InfoCard>

        <InfoCard title="스크리닝 지표">
          <InfoRow label="MA5" value={formatNumber(Math.round((scr?.ma5 as number) ?? 0))} />
          <InfoRow label="MA20" value={formatNumber(Math.round((scr?.ma20 as number) ?? 0))} />
          <InfoRow label="MA60" value={formatNumber(Math.round((scr?.ma60 as number) ?? 0))} />
          <InfoRow label="MA120" value={formatNumber(Math.round((scr?.ma120 as number) ?? 0))} />
          <InfoRow label="거래량비(5d)" value={scr?.volume_ratio_5d != null ? `${(scr.volume_ratio_5d as number).toFixed(1)}x` : "-"} />
        </InfoCard>

        <InfoCard title="수급 (누적)">
          <InfoRow label="외인 5일" value={formatNumber(scr?.foreign_net_5d as number)} color={colorByChange(scr?.foreign_net_5d as number)} />
          <InfoRow label="외인 20일" value={formatNumber(scr?.foreign_net_20d as number)} color={colorByChange(scr?.foreign_net_20d as number)} />
          <InfoRow label="기관 5일" value={formatNumber(scr?.institution_net_5d as number)} color={colorByChange(scr?.institution_net_5d as number)} />
        </InfoCard>
      </div>

      {(flow as Record<string, unknown>[]).length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-400 mb-2">투자자 수급 (최근 30일)</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="text-left py-1 px-2">날짜</th>
                <th className="text-right py-1 px-2">외국인</th>
                <th className="text-right py-1 px-2">기관</th>
                <th className="text-right py-1 px-2">개인</th>
              </tr>
            </thead>
            <tbody>
              {(flow as Record<string, unknown>[]).slice(0, 20).map((f, i) => (
                <tr key={i} className="border-b border-gray-900">
                  <td className="py-1 px-2">{f.date as string}</td>
                  <td className={`py-1 px-2 text-right ${colorByChange(f.foreign_net as number)}`}>
                    {formatNumber(f.foreign_net as number)}
                  </td>
                  <td className={`py-1 px-2 text-right ${colorByChange(f.institution_net as number)}`}>
                    {formatNumber(f.institution_net as number)}
                  </td>
                  <td className={`py-1 px-2 text-right ${colorByChange(f.individual_net as number)}`}>
                    {formatNumber(f.individual_net as number)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function InfoCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-900 rounded-lg p-4">
      <h3 className="text-xs text-gray-500 mb-2">{title}</h3>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function InfoRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-gray-400">{label}</span>
      <span className={color ?? ""}>{value}</span>
    </div>
  );
}
