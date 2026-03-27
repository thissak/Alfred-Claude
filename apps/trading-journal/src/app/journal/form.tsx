"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function TradeForm() {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const qty = Number(form.get("qty"));
    const price = Number(form.get("price"));

    const body = {
      code: form.get("code"),
      name: form.get("name"),
      side: form.get("side"),
      qty,
      price,
      total_amount: qty * price,
      traded_at: form.get("traded_at"),
      strategy: form.get("strategy") || null,
      emotion: form.get("emotion") || null,
      reason: form.get("reason") || null,
      post_note: null,
      pnl: form.get("pnl") ? Number(form.get("pnl")) : null,
      pnl_rate: null,
    };

    await fetch("/api/trades", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    setOpen(false);
    router.refresh();
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="px-4 py-2 bg-white text-black rounded text-sm font-medium hover:bg-gray-200"
      >
        + 매매 기록
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="bg-gray-900 rounded-lg p-4 space-y-3">
      <div className="grid grid-cols-6 gap-3">
        <Input name="code" placeholder="종목코드" required />
        <Input name="name" placeholder="종목명" required />
        <Select name="side" options={["buy", "sell", "cut"]} labels={["매수", "매도", "손절"]} />
        <Input name="qty" placeholder="수량" type="number" required />
        <Input name="price" placeholder="가격" type="number" required />
        <Input name="traded_at" type="date" required defaultValue={new Date().toISOString().slice(0, 10)} />
      </div>
      <div className="grid grid-cols-4 gap-3">
        <Select
          name="strategy"
          options={["", "momentum", "value", "swing", "breakout", "hedge"]}
          labels={["전략 선택", "모멘텀", "가치", "스윙", "돌파", "헤지"]}
        />
        <Select
          name="emotion"
          options={["", "confident", "calm", "fomo", "fearful", "impulsive"]}
          labels={["감정 선택", "확신", "침착", "FOMO", "불안", "충동"]}
        />
        <Input name="pnl" placeholder="실현손익 (매도시)" type="number" />
        <Input name="reason" placeholder="매매 사유" />
      </div>
      <div className="flex gap-2">
        <button type="submit" className="px-4 py-1.5 bg-white text-black rounded text-sm">
          저장
        </button>
        <button type="button" onClick={() => setOpen(false)} className="px-4 py-1.5 bg-gray-800 text-gray-400 rounded text-sm">
          취소
        </button>
      </div>
    </form>
  );
}

function Input(props: React.InputHTMLAttributes<HTMLInputElement> & { name: string }) {
  return (
    <input
      {...props}
      className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-gray-500"
    />
  );
}

function Select({
  name,
  options,
  labels,
}: {
  name: string;
  options: string[];
  labels: string[];
}) {
  return (
    <select
      name={name}
      className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-gray-500"
    >
      {options.map((o, i) => (
        <option key={o} value={o}>
          {labels[i]}
        </option>
      ))}
    </select>
  );
}
