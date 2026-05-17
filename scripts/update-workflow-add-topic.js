// Run with: npx dotenv-cli node scripts/update-workflow-add-topic.js
// Updates 3 nodes to add granular "topic" field to AI enrichment:
//   1. Prepare Prompt  — adds "topic" to the JSON schema in the prompt
//   2. Parse Gemini Response — extracts enriched.topic → ai_topic
//   3. Update Sheet (Success) — writes ai_topic column to the Sheet

const WORKFLOW_ID = 'SDRa5ZYGhX79m8F6';
const N8N_BASE = 'http://localhost:5678';
const API_KEY = process.env.N8N_API_KEY;

if (!API_KEY) { console.error('N8N_API_KEY not set — add it to .env'); process.exit(1); }

const HEADERS = {
  'X-N8N-API-KEY': API_KEY,
  'Content-Type': 'application/json',
};

const NEW_PREPARE_PROMPT_CODE = `const item = $input.item.json;
const transcript = item.transcript || '';

// 1. Error Handling & Skip Logic
if (!transcript || item.status !== 'ok') {
  return {
    json: {
      ...item,
      skip_enrichment: true,
      prompt: ''
    }
  };
}

// 2. Transcript Truncation (Safety Gate)
const MAX_CHARS = 12000;
const truncated = transcript.length > MAX_CHARS
  ? transcript.slice(0, MAX_CHARS) + '\\n\\n[transcript truncated]'
  : transcript;

// 3. Structured Prompt Construction
const prompt = \`Analyze this YouTube transcript for a video titled: "\${item.title || 'Unknown'}".

### STEP 1: CLASSIFICATION
Determine if this video is:
A) Technical Tutorial / Coding walkthrough
B) Market Analysis / Trading strategy
C) General Educational / News content

### STEP 2: TOPIC
Identify the specific subject in 2–5 words. Be concrete, not categorical.
Good: "claude code + n8n", "shadcn table component", "RSI divergence strategy"
Bad: "coding tutorial", "market analysis", "general tips"

### STEP 3: EXTRACTION RULES
- If (A): Focus heavily on software architecture, specific libraries, and repository URLs.
- If (B): Focus on tickers ($), entry/exit strategies, macro indicators, and price targets.
- If (C): Focus on core concepts and a high-level summary.

### STEP 4: OUTPUT FORMAT
Respond ONLY with a valid JSON object. No markdown, no backticks, no text before or after the JSON.

{
  "category": "Detected Category",
  "topic": "specific subject in 2-5 words",
  "objective": "One sentence: what is the specific goal of this video?",
  "action_points": ["Key takeaway 1", "Key takeaway 2", "Key takeaway 3"],
  "tools": [
    {
      "name": "Tool/Library/Ticker name",
      "type": "tool|repo|library|symbol|service",
      "url": "URL if mentioned, else empty string",
      "description": "One sentence role/context"
    }
  ],
  "market_data": "Summary of symbols, trends, or price levels if Category B, else empty string"
}

### TRANSCRIPT:
\${truncated}\`;

return {
  json: {
    ...item,
    skip_enrichment: false,
    prompt: prompt
  }
};`;

const NEW_PARSE_GEMINI_CODE = `const item = $('Prepare Prompt').item.json;
  const response = $input.item.json;

  if (item.skip_enrichment) {
    return {
      json: {
        ...item,
        ai_category: '',
        ai_topic: '',
        ai_objective: '',
        ai_action_points: '',
        ai_tools: '',
        ai_market_data: ''
      }
    };
  }

  let enriched = { category: '', topic: '', objective: '', action_points: [], tools: [], market_data: '' };

  try {
    const rawText = response?.content?.parts?.[0]?.text || '{}';

    // Strip markdown code fences
    let clean = rawText.replace(/^\`\`\`json\\s*/i, '').replace(/\`\`\`\\s*$/i, '').trim();

    // Extract the first {...} block — handles extra text before/after the JSON
    const jsonMatch = clean.match(/\\{[\\s\\S]*\\}/);
    if (jsonMatch) clean = jsonMatch[0];

    enriched = JSON.parse(clean);
  } catch (err) {
    enriched = {
      objective: \`enrichment_error: \${err.message}\`,
      action_points: [],
      tools: []
    };
  }

  const action_points_str = (enriched.action_points || []).join(' | ');

  const tools_str = (enriched.tools || []).map(t => {
    const url_part = t.url ? \` (\${t.url})\` : '';
    const type_label = t.type === 'symbol' ? '$' : \`[\${t.type || 'tool'}] \`;
    return \`\${type_label}\${t.name}\${url_part}: \${t.description || ''}\`;
  }).join(' | ');

  return {
    json: {
      ...item,
      ai_category: enriched.category || 'General',
      ai_topic: enriched.topic || '',
      ai_objective: enriched.objective || '',
      ai_action_points: action_points_str,
      ai_tools: tools_str,
      ai_market_data: enriched.market_data || ''
    }
  };`;

async function main() {
  // 1. GET the workflow
  const getRes = await fetch(`${N8N_BASE}/api/v1/workflows/${WORKFLOW_ID}`, { headers: HEADERS });
  if (!getRes.ok) throw new Error(`GET failed ${getRes.status}: ${await getRes.text()}`);
  const wf = await getRes.json();

  // 2. Patch Prepare Prompt
  const prepareNode = wf.nodes.find(n => n.name === 'Prepare Prompt');
  if (!prepareNode) throw new Error("Node 'Prepare Prompt' not found");
  prepareNode.parameters.jsCode = NEW_PREPARE_PROMPT_CODE;
  console.log('✓ Patched: Prepare Prompt');

  // 3. Patch Parse Gemini Response
  const parseNode = wf.nodes.find(n => n.name === 'Parse Gemini Response');
  if (!parseNode) throw new Error("Node 'Parse Gemini Response' not found");
  parseNode.parameters.jsCode = NEW_PARSE_GEMINI_CODE;
  console.log('✓ Patched: Parse Gemini Response');

  // 4. Patch Update Sheet (Success) — add ai_topic to column mapping
  const sheetNode = wf.nodes.find(n => n.name === 'Update Sheet (Success)');
  if (!sheetNode) throw new Error("Node 'Update Sheet (Success)' not found");
  sheetNode.parameters.columns.value['ai_topic'] = '={{ $json.ai_topic }}';

  // Add ai_topic to schema if not already present
  const schema = sheetNode.parameters.columns.schema;
  if (!schema.find(s => s.id === 'ai_topic')) {
    schema.push({
      id: 'ai_topic',
      displayName: 'ai_topic',
      required: false,
      defaultMatch: false,
      display: true,
      type: 'string',
      canBeUsedToMatch: true,
      removed: false,
    });
  }
  console.log('✓ Patched: Update Sheet (Success)');

  // 5. PUT the updated workflow
  const putBody = {
    name: wf.name,
    nodes: wf.nodes,
    connections: wf.connections,
    settings: { executionOrder: wf.settings?.executionOrder ?? 'v1' },
    staticData: wf.staticData ?? null,
  };

  const putRes = await fetch(`${N8N_BASE}/api/v1/workflows/${WORKFLOW_ID}`, {
    method: 'PUT',
    headers: HEADERS,
    body: JSON.stringify(putBody),
  });

  if (!putRes.ok) throw new Error(`PUT failed ${putRes.status}: ${await putRes.text()}`);
  const updated = await putRes.json();
  console.log(`\nDone. Active: ${updated.active} | Nodes: ${updated.nodes.length}`);
}

main().catch(err => { console.error(err.message); process.exit(1); });
