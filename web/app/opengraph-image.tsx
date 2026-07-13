import { ImageResponse } from 'next/og';

// The link-preview card IS the first impression for a product shared into
// Telegram chats — render it in the page's own voice (canvas plate, headline
// triad, one amber mark). Satori ships one regular-weight default font, so
// hierarchy comes from size and color, never fontWeight.
export const runtime = 'edge';
export const alt = 'Ownix — your internet, indexed';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          backgroundColor: '#0d0e10',
          padding: 72,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
          <div
            style={{
              width: 16,
              height: 16,
              backgroundColor: '#d99a45',
              borderRadius: 4,
            }}
          />
          <div style={{ fontSize: 34, color: '#f4f1eb' }}>Ownix</div>
          <div style={{ fontSize: 26, color: '#948e84' }}>
            invite-only for now
          </div>
        </div>
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
          }}
        >
          <div style={{ fontSize: 82, color: '#f4f1eb' }}>
            You watched it.
          </div>
          <div style={{ fontSize: 82, color: '#f4f1eb' }}>
            You liked it.
          </div>
          <div style={{ fontSize: 82, color: '#948e84' }}>
            You lost it.
          </div>
        </div>
        <div style={{ display: 'flex', fontSize: 30, color: '#c6c1b8' }}>
          your internet, indexed — transcripts, summaries, links, repos
        </div>
      </div>
    ),
    size,
  );
}
