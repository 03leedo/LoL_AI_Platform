"use client";

import { Search } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export function GlobalNav() {
  const router = useRouter();
  const pathname = usePathname();
  const [query, setQuery] = useState("");

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const raw = query.trim();
    if (!raw.includes("#")) {
      return;
    }
    const hashIndex = raw.lastIndexOf("#");
    const gameName = raw.slice(0, hashIndex).trim();
    const tagLine = raw.slice(hashIndex + 1).trim();
    if (!gameName || !tagLine) {
      return;
    }
    const params = new URLSearchParams({ gameName, tagLine });
    setQuery("");
    router.push(`/summoner?${params.toString()}`);
  }

  return (
    <nav className="global-nav">
      <div className="global-nav-inner">
        <Link href="/" className="global-nav-logo">
          <strong>LoL</strong>.<em>AI</em>
        </Link>
        {pathname !== "/" && (
          <form className="global-nav-search" onSubmit={onSubmit}>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder='소환사 검색 — 게임이름#태그'
              aria-label="소환사 검색"
            />
            <button type="submit" aria-label="검색">
              <Search size={15} aria-hidden="true" />
            </button>
          </form>
        )}
      </div>
    </nav>
  );
}
