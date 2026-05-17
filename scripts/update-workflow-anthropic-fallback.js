// Run with: N8N_API_KEY=... node scripts/update-workflow-anthropic-fallback.js
// OR use a .env loader like dotenv-cli:  npx dotenv-cli node scripts/update-workflow-anthropic-fallback.js

const WORKFLOW_ID = 'SDRa5ZYGhX79m8F6';
const N8N_BASE = 'http://localhost:5678';
const API_KEY = process.env.N8N_API_KEY;

if (!process.env.N8N_API_KEY) { console.error('N8N_API_KEY not set — add it to .env'); process.exit(1); }

const HEADERS = {
  'X-N8N-API-KEY': API_KEY,
  'Content-Type': 'application/json',
};

async function main() {
  // 1. GET the workflow
  const getRes = await fetch(`${N8N_BASE}/api/v1/workflows/${WORKFLOW_ID}`, { headers: HEADERS });
  if (!getRes.ok) {
    const body = await getRes.text();
    throw new Error(`GET failed ${getRes.status}: ${body}`);
  }
  const wf = await getRes.json();

  // 2. Remove old node
  wf.nodes = wf.nodes.filter(n => n.name !== 'Recover on Gemini Error');

  // 3. Define new nodes
  const NODE_ANTHROPIC = {
    id: 'anthropic-fallback-001',
    name: 'Message Anthropic',
    type: 'n8n-nodes-base.httpRequest',
    typeVersion: 4.2,
    position: [3408, 1696],
    retryOnFail: true,
    maxTries: 3,
    onError: 'continueRegularOutput',
    executeOnce: true,
    parameters: {
      method: 'POST',
      url: 'https://api.anthropic.com/v1/messages',
      authentication: 'genericCredentialType',
      genericAuthType: 'anthropicApi',
      sendHeaders: true,
      headerParameters: {
        parameters: [
          { name: 'anthropic-version', value: '2023-06-01' },
          { name: 'content-type', value: 'application/json' },
        ],
      },
      sendBody: true,
      contentType: 'raw',
      rawContentType: 'application/json',
      body: "={{ JSON.stringify({ model: 'claude-sonnet-4-5', max_tokens: 4096, messages: [{ role: 'user', content: $('Prepare Prompt').item.json.prompt }] }) }}",
      options: {
        response: {
          response: {
            // neverError: true routes 4xx/5xx to normal output so the downstream IF node
            // can detect the empty response and fall through to Recover on Double Failure
            neverError: true,
            responseFormat: 'json',
          },
        },
      },
    },
    credentials: {
      anthropicApi: { id: '3EI6IzFB71TWRAgn', name: 'Anthropic account' },
    },
  };

  const NODE_ANTHROPIC_IF = {
    id: 'anthropic-if-001',
    name: 'Anthropic Text Response?',
    type: 'n8n-nodes-base.if',
    typeVersion: 2.3,
    position: [3660, 1696],
    parameters: {
      conditions: {
        options: { caseSensitive: true, leftValue: '', typeValidation: 'strict', version: 3 },
        conditions: [{
          id: 'anthropic-text-check',
          leftValue: '={{ $json.content[0].text }}',
          rightValue: '',
          operator: { type: 'string', operation: 'notEmpty', singleValue: true },
        }],
        combinator: 'and',
      },
      options: {},
    },
  };

  const NODE_NORMALIZE = {
    id: 'normalize-anthropic-001',
    name: 'Normalize Anthropic Response',
    type: 'n8n-nodes-base.code',
    typeVersion: 2,
    position: [3910, 1600],
    parameters: {
      mode: 'runOnceForEachItem',
      jsCode: `const text = $input.item.json.content[0].text;\nreturn { json: { content: { parts: [{ text }] } } };`,
    },
  };

  const NODE_DOUBLE_FAIL = {
    id: 'double-fail-001',
    name: 'Recover on Double Failure',
    type: 'n8n-nodes-base.code',
    typeVersion: 2,
    position: [3910, 1792],
    parameters: {
      mode: 'runOnceForEachItem',
      jsCode: `const merged = $('Merge Drive Result1').item.json;\nreturn { json: { ...merged, ai_objective: 'enrichment_error: Gemini and Anthropic unavailable', ai_action_points: '', ai_tools: '' } };`,
    },
  };

  const NODE_TELEGRAM_ALERT = {
    id: 'telegram-ai-fail-001',
    name: 'Telegram: AI Enrichment Failed',
    type: 'n8n-nodes-base.telegram',
    typeVersion: 1.2,
    position: [4160, 1792],
    parameters: {
      chatId: "={{ $('Telegram Trigger1').item.json.message.chat.id }}",
      text: "=⚠️ Both Gemini and Anthropic failed to enrich: {{ $('Merge Drive Result1').item.json.title || '(unknown video)' }}",
      additionalFields: { parse_mode: 'HTML' },
    },
    credentials: {
      telegramApi: { id: 'URx0wuRRZV0EoTUg', name: 'Telegram account' },
    },
  };

  // Add new nodes
  wf.nodes.push(NODE_ANTHROPIC, NODE_ANTHROPIC_IF, NODE_NORMALIZE, NODE_DOUBLE_FAIL, NODE_TELEGRAM_ALERT);

  // 4. Rewire connections
  const conn = wf.connections;

  // Gemini Text Response? false → Message Anthropic
  if (!conn['Gemini Text Response?']?.main) {
    throw new Error("Expected connection 'Gemini Text Response?' not found — workflow structure may have changed");
  }
  conn['Gemini Text Response?'].main[1] = [{ node: 'Message Anthropic', type: 'main', index: 0 }];

  // Message Anthropic → Anthropic Text Response?
  conn['Message Anthropic'] = { main: [[{ node: 'Anthropic Text Response?', type: 'main', index: 0 }]] };

  // Anthropic Text Response? → true: Normalize | false: Recover on Double Failure
  conn['Anthropic Text Response?'] = {
    main: [
      [{ node: 'Normalize Anthropic Response', type: 'main', index: 0 }],
      [{ node: 'Recover on Double Failure', type: 'main', index: 0 }],
    ],
  };

  // Normalize → Parse Gemini Response (existing node, reused)
  conn['Normalize Anthropic Response'] = { main: [[{ node: 'Parse Gemini Response', type: 'main', index: 0 }]] };

  // Recover on Double Failure → Update Sheet (Success) + Telegram alert (parallel)
  conn['Recover on Double Failure'] = {
    main: [[
      { node: 'Update Sheet (Success)', type: 'main', index: 0 },
      { node: 'Telegram: AI Enrichment Failed', type: 'main', index: 0 },
    ]],
  };

  // Telegram: AI Enrichment Failed → terminal
  conn['Telegram: AI Enrichment Failed'] = { main: [[]] };

  // Remove old connection
  delete conn['Recover on Gemini Error'];

  // 5. PUT the updated workflow
  // The n8n API only accepts a subset of fields; settings must only have executionOrder
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

  if (!putRes.ok) {
    const body = await putRes.text();
    throw new Error(`PUT failed ${putRes.status}: ${body}`);
  }

  const updated = await putRes.json();

  // 6. Log result
  console.log(`Done. Active: ${updated.active} | Nodes: ${updated.nodes.length}`);
}

main().catch(err => {
  console.error(err.message);
  process.exit(1);
});
