import { Loader2, Search } from "lucide-react";

export function EmptyState({ label }: { label: string }) {
  return (
    <div className="empty-state">
      <Search size={28} aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}

export function LoadingState({ label }: { label: string }) {
  return (
    <div className="loading-state">
      <Loader2 className="spin" size={24} aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}
