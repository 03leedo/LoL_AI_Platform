"use client";

import { Loader2, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export default function Home() {
  const router = useRouter();
  const [gameName, setGameName] = useState("");
  const [tagLine, setTagLine] = useState("");
  const [isNavigating, setIsNavigating] = useState(false);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const normalizedGameName = gameName.trim();
    const normalizedTagLine = tagLine.trim();

    if (!normalizedGameName || !normalizedTagLine) {
      return;
    }

    setIsNavigating(true);
    const params = new URLSearchParams({
      gameName: normalizedGameName,
      tagLine: normalizedTagLine
    });
    router.push(`/summoner?${params.toString()}`);
  }

  return (
    <main className="app-shell">
      <section className="search-hero">
        <div className="hero-copy">
          <p className="eyebrow">LoL AI Platform</p>
          <h1>소환사 전적 분석</h1>
          <p>최근 경기 기록을 불러오고, 선택한 판의 흐름과 손해 포인트를 바로 복기합니다.</p>
        </div>

        <form className="summoner-search" onSubmit={onSubmit}>
          <div className="search-fields">
            <label htmlFor="gameName">Riot ID</label>
            <input
              id="gameName"
              name="gameName"
              value={gameName}
              onChange={(event) => setGameName(event.target.value)}
              placeholder="Hide on bush"
              autoComplete="off"
              required
            />
          </div>

          <div className="search-fields tag-field">
            <label htmlFor="tagLine">Tag</label>
            <input
              id="tagLine"
              name="tagLine"
              value={tagLine}
              onChange={(event) => setTagLine(event.target.value)}
              placeholder="KR1"
              autoComplete="off"
              required
            />
          </div>

          <button type="submit" disabled={isNavigating}>
            {isNavigating ? (
              <Loader2 className="spin" size={18} aria-hidden="true" />
            ) : (
              <Search size={18} aria-hidden="true" />
            )}
            <span>검색</span>
          </button>
        </form>
      </section>
    </main>
  );
}
