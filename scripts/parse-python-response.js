// Runs once per input item.
const apifyResponse = $input.item.json;
const inputRow = $('Filter Pending Rows').item.json;
const meta = $('Extract Description Links').item.json;

const datasetItem = Array.isArray(apifyResponse)
  ? apifyResponse[0]
  : apifyResponse;

let transcript = '';
let status = 'ok';

if (!datasetItem) {
  status = 'error: no dataset item returned';
} else if (datasetItem.error) {
  status = `error: ${datasetItem.error.type || 'unknown'} - ${datasetItem.error.message || ''}`;
} else {
  transcript = datasetItem.text || datasetItem.transcript || '';
  if (!transcript)
    status = 'error: transcript empty (captions may be disabled)';
}

// Metadata from /metadata endpoint (falls back to empty strings if errored)
const title = meta.title || '';
const channel = meta.channel || '';
const views = meta.views || '';

const video_id =
  datasetItem?.videoId ||
  ((inputRow.url || '').match(/[?&]v=([^&]+)/) || [])[1] ||
  '';

const slugify = (s) =>
  String(s)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 80);

const title_slug = slugify(title) || 'untitled';
const filename = `${title_slug}.md`;

const fetched_at = new Date().toISOString();
const char_count = transcript.length;

const markdown =
  `# ${title || 'Untitled'}\n\n` +
  `**Channel:** ${channel || 'Unknown'}\n` +
  `**Views:** ${views}\n` +
  `**Video ID:** ${video_id}\n` +
  `**URL:** ${inputRow.url}\n` +
  `**Fetched:** ${fetched_at}\n` +
  `**Char count:** ${char_count}\n\n` +
  `---\n\n` +
  `${transcript}\n`;

return {
  json: {
    row_number: inputRow.row_number,
    url: inputRow.url,
    video_id,
    title,
    channel,
    duration: '',
    char_count,
    filename,
    markdown,
    transcript,
    fetched_at,
    status,
    description_links: meta.description_links || [],
    description_links_raw: meta.description_links_raw || '',
  },
};
