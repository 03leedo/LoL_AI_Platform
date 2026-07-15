"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

export default function LegacySummonerRoute() {
  const router = useRouter();
  const params = useParams<{ riotId: string }>();

  useEffect(() => {
    const riotId = typeof params?.riotId === "string" ? params.riotId : "";
    const separatorIndex = riotId.lastIndexOf("-");

    if (separatorIndex <= 0 || separatorIndex === riotId.length - 1) {
      router.replace("/");
      return;
    }

    const gameName = safeDecode(riotId.slice(0, separatorIndex));
    const tagLine = safeDecode(riotId.slice(separatorIndex + 1));
    const query = new URLSearchParams({ gameName, tagLine });
    router.replace(`/summoner?${query.toString()}`);
  }, [params, router]);

  return null;
}

function safeDecode(value: string) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}
