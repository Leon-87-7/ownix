import Link from "next/link";

export interface SpaceSummary {
  id: string;
  name: string;
  color: string;
  created_at: string;
}

export function SpaceCard({ space }: { space: SpaceSummary }) {
  return (
    <Link href={`/spaces/${space.id}`}>
      <div className="flex items-center gap-3 rounded-lg bg-gray-800 px-4 py-3 hover:bg-gray-750 transition-colors cursor-pointer">
        <span
          className="inline-block h-3 w-3 flex-shrink-0 rounded-full"
          style={{ backgroundColor: space.color }}
        />
        <span className="truncate text-sm font-medium text-gray-100">
          {space.name}
        </span>
      </div>
    </Link>
  );
}
