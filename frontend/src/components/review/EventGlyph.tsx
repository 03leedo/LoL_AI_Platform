import { Castle, Crosshair, Eye, Flame, Skull } from "lucide-react";

export function EventGlyph({ type }: { type: string }) {
  if (type === "kill") {
    return <Skull size={15} aria-hidden="true" />;
  }
  if (type === "tower" || type === "inhibitor") {
    return <Castle size={15} aria-hidden="true" />;
  }
  if (["dragon", "herald", "baron", "voidgrub", "atakhan"].includes(type)) {
    return <Flame size={15} aria-hidden="true" />;
  }
  if (type.startsWith("ward_")) {
    return <Eye size={15} aria-hidden="true" />;
  }
  return <Crosshair size={15} aria-hidden="true" />;
}
