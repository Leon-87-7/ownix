import OwnixLogo from '@/app/ownix-logo.svg';
import { McpIcon } from '@/components/svg/mcp-icon';

const clients = ['Claude Code', 'Cursor', 'Codex', 'VS Code'];

const capabilities: { label: string; tool?: string; body: string }[] = [
  {
    tool: 'scout',
    label: 'scout',
    body: 'Search your own Index and jobs by meaning, not keyword.',
  },
  {
    label: 'Spaces',
    body: 'Create, list and reorder Spaces without leaving the chat.',
  },
  {
    label: 'Context blobs',
    body: 'Pin a blob of context to a Space your agent will read next time.',
  },
];

/** Pitches Ownix as an MCP server, not only a dashboard - for the "agent
 * builders" audience who live in Claude Code / Cursor / Codex rather than
 * a browser tab. Mirrors the split layout of the features section above
 * it: prose + capability list on the left, a small hub-and-spoke diagram
 * (Ownix -> MCP -> the client the agent is running in) on the right.
 * `tool` on a capability marks it as a literal callable name (rendered in
 * code font); the entries without it are a capability area covering
 * several real tools, kept in plain text so the styling itself signals
 * which is which. */
export function McpSection() {
  return (
    <section
      aria-labelledby="mcp"
      className="border-t border-line py-16"
    >
      <div className="mx-auto grid max-w-[960px] gap-8 px-6 md:grid-cols-[1.1fr_1fr] md:items-start">
        <div>
          <span className="mb-2 block font-mono text-mono-label font-medium tracking-[0.4px] text-contrasignal">
            FOR AGENT BUILDERS
          </span>
          <h2
            id="mcp"
            className="text-pretty mb-3 max-w-[16ch] font-title text-[clamp(1.375rem,3.4vw,1.75rem)] font-semibold leading-tight tracking-[-0.25px] text-ink"
          >
            One Index, wherever you already work.
          </h2>
          <p className="text-pretty max-w-[52ch] text-prose leading-relaxed text-body">
            Ownix runs as an MCP server. Connect it once and your agent
            can read, search, or curate your own Index right where
            you&apos;re already working. No tab switch, no lost context
            mid-task.
          </p>

          <ul className="mt-5 flex flex-col gap-2.5">
            {capabilities.map(({ label, tool, body }) => (
              <li
                key={label}
                className="flex items-baseline gap-2.5 text-copy text-body"
              >
                {tool ? (
                  <code className="shrink-0 rounded-sm border border-line bg-raised px-1.5 py-0.5 font-mono text-xs text-contrasignal">
                    {tool}
                  </code>
                ) : (
                  <span className="shrink-0 rounded-sm border border-line bg-raised px-1.5 py-0.5 text-xs font-medium text-contrasignal">
                    {label}
                  </span>
                )}
                {body}
              </li>
            ))}
          </ul>
        </div>

        <div className="flex flex-col items-center gap-0 md:pt-12">
          <div className="inline-flex items-center gap-2.5 rounded-lg border border-line bg-surface px-3.5 py-2.5 text-copy font-medium text-ink">
            <OwnixLogo
              aria-hidden="true"
              className="h-[26px] w-[26px] shrink-0 rounded-full border border-line bg-canvas p-1"
            />
            Ownix Index
          </div>

          <div className="my-1 flex items-center gap-2.5">
            <span
              aria-hidden="true"
              className="h-[22px] w-px bg-line-strong"
            />
            <span className="grid h-8 w-8 place-items-center rounded-full bg-ink shadow-[0_0_0_4px_rgba(148,230,238,0.15)]">
              <McpIcon className="h-[15px] w-[15px] text-onsignal" />
            </span>
            <span
              aria-hidden="true"
              className="h-[22px] w-px bg-line-strong"
            />
          </div>

          <div
            aria-label={`Ownix connected to ${clients.join(', ')} over MCP`}
            className="flex flex-wrap justify-center gap-2"
          >
            {clients.map((name) => (
              <span
                key={name}
                className="inline-flex items-center rounded-full border border-line bg-raised px-3 py-1.5 text-xs font-medium text-ink"
              >
                {name}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
