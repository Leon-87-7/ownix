// Served from the service-worker cache when a navigation fails offline
// (public/sw.js). Deliberately self-contained: inline styles + system font
// stacks only, because the cached HTML's /_next/static CSS and font assets
// are NOT cached and won't load offline (and go stale after every deploy).
// Values mirror the DESIGN.md tokens in tailwind.config.ts.
export default function OfflinePage() {
  return (
    <main
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#0d0e10',
        color: '#f4f1eb',
        padding: '0 24px',
        fontFamily: 'system-ui, sans-serif',
      }}
    >
      <section
        style={{
          width: '100%',
          maxWidth: '28rem',
          border: '1px solid #30343d',
          background: '#16181c',
          borderRadius: '12px',
          padding: '24px',
        }}
      >
        <p
          style={{
            fontFamily:
              "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace",
            fontSize: '0.75rem',
            textTransform: 'uppercase',
            letterSpacing: '0.24em',
            color: '#948e84',
            margin: 0,
          }}
        >
          status: offline
        </p>
        <h1
          style={{
            marginTop: '16px',
            marginBottom: 0,
            fontSize: '1.5rem',
            fontWeight: 600,
            letterSpacing: '-0.01em',
          }}
        >
          Ownix is waiting for a connection.
        </h1>
        <p
          style={{
            marginTop: '12px',
            marginBottom: 0,
            fontSize: '0.875rem',
            lineHeight: '1.5rem',
            color: '#c6c1b8',
          }}
        >
          Your Index needs live data, so cached payloads stay off the
          console.
        </p>
        <a
          href="/feed"
          style={{
            marginTop: '24px',
            display: 'inline-flex',
            height: '36px',
            alignItems: 'center',
            borderRadius: '6px',
            border: '1px solid #30343d',
            background: '#0d0e10',
            padding: '0 12px',
            fontSize: '0.875rem',
            fontWeight: 500,
            color: '#c6c1b8',
            textDecoration: 'none',
          }}
        >
          Retry Feed
        </a>
      </section>
    </main>
  );
}
