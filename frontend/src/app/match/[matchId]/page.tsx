"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

export default function LegacyMatchRoute() {
  const router = useRouter();
  const params = useParams<{ matchId: string }>();
  const searchParams = useSearchParams();

  useEffect(() => {
    const matchId = typeof params?.matchId === "string" ? safeDecode(params.matchId) : "";
    const puuid = searchParams.get("puuid") ?? "";
    const riotId = searchParams.get("riotId") ?? "";
    const query = new URLSearchParams();

    if (matchId) {
      query.set("matchId", matchId);
    }
    if (puuid) {
      query.set("puuid", puuid);
    }

    const parsedRiotId = parseRiotId(riotId);
    if (parsedRiotId) {
      query.set("gameName", parsedRiotId.gameName);
      query.set("tagLine", parsedRiotId.tagLine);
    }

    router.replace(query.size > 0 ? `/match?${query.toString()}` : "/");
  }, [params, router, searchParams]);

  return null;
}

function parseRiotId(riotId: string) {
  const separatorIndex = riotId.lastIndexOf("-");
  if (separatorIndex <= 0 || separatorIndex === riotId.length - 1) {
    return null;
  }

  return {
    gameName: safeDecode(riotId.slice(0, separatorIndex)),
    tagLine: safeDecode(riotId.slice(separatorIndex + 1))
  };
}

function safeDecode(value: string) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}
