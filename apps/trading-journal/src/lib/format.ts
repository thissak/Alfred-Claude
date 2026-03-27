export function formatNumber(n: number | null | undefined): string {
  if (n == null) return "-";
  return n.toLocaleString("ko-KR");
}

export function formatPercent(n: number | null | undefined): string {
  if (n == null) return "-";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

export function formatPrice(n: number | null | undefined): string {
  if (n == null) return "-";
  return n.toLocaleString("ko-KR");
}

export function colorByChange(rate: number | null | undefined): string {
  if (rate == null) return "";
  if (rate > 0) return "text-red-500";
  if (rate < 0) return "text-blue-500";
  return "";
}
