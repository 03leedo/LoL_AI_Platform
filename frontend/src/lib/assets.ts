const MAP_SIZE = 15000;

export function mapCoord(value: number | null) {
  if (value === null) {
    return 50;
  }
  return Math.max(0, Math.min(100, (value / MAP_SIZE) * 100));
}

export function championInitial(championName: string | null, participantId: number) {
  if (!championName) {
    return String(participantId);
  }
  return championName.slice(0, 2).toUpperCase();
}

export function championIconUrl(championName: string, version: string) {
  return `https://ddragon.leagueoflegends.com/cdn/${version}/img/champion/${championAssetName(championName)}.png`;
}

export function mapImageUrl(mapId: number) {
  return `https://ddragon.leagueoflegends.com/cdn/6.8.1/img/map/map${mapId}.png`;
}

export function championSplashUrl(championName: string) {
  const assetName = championAssetName(championName);
  return `https://ddragon.leagueoflegends.com/cdn/img/champion/splash/${assetName}_0.jpg`;
}

function championAssetName(championName: string) {
  const overrides: Record<string, string> = {
    FiddleSticks: "Fiddlesticks"
  };
  return overrides[championName] ?? championName.replace(/[^A-Za-z0-9]/g, "");
}
