interface StatCardProps {
  label: string;
  value: number;
  className?: string;
}

export function StatCard({ label, value, className = "" }: StatCardProps) {
  return (
    <div
      className={`rounded-lg bg-gray-800 px-4 py-3 flex flex-col gap-1 ${className}`}
    >
      <span className="text-xs uppercase tracking-wide text-gray-400">{label}</span>
      <span className="text-2xl font-bold text-white tabular-nums">{value}</span>
    </div>
  );
}
