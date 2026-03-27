import type { Metadata } from "next";
import Link from "next/link";
import SearchBar from "@/components/SearchBar";
import "./globals.css";

export const metadata: Metadata = {
  title: "Trading Journal",
  description: "매매일지 + 종목 분석 대시보드",
};

const NAV = [
  { href: "/", label: "시장 개요" },
  { href: "/screening", label: "스크리닝" },
  { href: "/journal", label: "매매일지" },
  { href: "/performance", label: "성과분석" },
  { href: "/psychology", label: "심리분석" },
];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="bg-gray-950 text-gray-100 min-h-screen">
        <nav className="border-b border-gray-800 px-6 py-3 flex items-center gap-6">
          <span className="text-lg font-bold text-white">Trading Journal</span>
          {NAV.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className="text-sm text-gray-400 hover:text-white transition-colors"
            >
              {n.label}
            </Link>
          ))}
          <div className="ml-auto">
            <SearchBar />
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-6 py-6">{children}</main>
      </body>
    </html>
  );
}
