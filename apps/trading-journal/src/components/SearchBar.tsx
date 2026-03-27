"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Result {
  code: string;
  name: string;
  market: string;
  mktcap: number;
}

export default function SearchBar() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Result[]>([]);
  const [open, setOpen] = useState(false);

  async function handleChange(q: string) {
    setQuery(q);
    if (q.length < 1) {
      setResults([]);
      setOpen(false);
      return;
    }
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    setResults(data);
    setOpen(data.length > 0);
  }

  function handleSelect(code: string) {
    setOpen(false);
    setQuery("");
    router.push(`/stock/${code}`);
  }

  return (
    <div className="relative">
      <input
        type="text"
        value={query}
        onChange={(e) => handleChange(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
        placeholder="종목 검색..."
        className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-gray-500 w-56"
      />
      {open && (
        <div className="absolute top-full left-0 mt-1 w-72 bg-gray-900 border border-gray-700 rounded shadow-lg z-50 max-h-64 overflow-y-auto">
          {results.map((r) => (
            <button
              key={r.code}
              onClick={() => handleSelect(r.code)}
              className="w-full text-left px-3 py-2 hover:bg-gray-800 text-sm flex justify-between"
            >
              <span>
                <span className="text-white">{r.name}</span>
                <span className="text-gray-500 ml-2">{r.code}</span>
              </span>
              <span className="text-gray-600 text-xs">{r.market}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
