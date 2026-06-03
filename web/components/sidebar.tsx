import Link from "next/link";

const NAV = [
  { href: "/", label: "Feed" },
  { href: "/brain", label: "Brain" },
  { href: "/spaces", label: "Spaces" },
  { href: "/prompts", label: "Prompts" },
  { href: "/controls", label: "Controls" },
];

export function Sidebar() {
  return (
    <aside className="flex w-52 flex-col border-r border-gray-800 bg-gray-900 px-4 py-6">
      <span className="mb-8 text-lg font-bold tracking-tight">vig</span>
      <nav className="flex flex-col gap-1">
        {NAV.map(({ href, label }) => (
          <Link
            key={href}
            href={href}
            className="rounded-md px-3 py-2 text-sm text-gray-300 hover:bg-gray-800 hover:text-white"
          >
            {label}
          </Link>
        ))}
      </nav>
      <div className="mt-auto">
        <form action="/api/auth/logout" method="POST">
          <button
            type="submit"
            className="w-full rounded-md px-3 py-2 text-left text-sm text-gray-400 hover:bg-gray-800 hover:text-white"
          >
            Sign out
          </button>
        </form>
      </div>
    </aside>
  );
}
