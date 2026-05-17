function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('AI Tools')
    .addItem('Fill missing topics', 'fillTopics')
    .addToUi();
}

function fillTopics() {
  const sheet =
    SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const headers = sheet
    .getRange(1, 1, 1, sheet.getLastColumn())
    .getValues()[0];
  Logger.log('Headers found: ' + JSON.stringify(headers));

  const col = (name) => headers.indexOf(name);
  const titleCol = col('title');
  const objCol = col('ai_objective');
  const toolsCol = col('ai_tools');
  const topicCol = col('ai_topic');
  Logger.log(
    `Columns — title:${titleCol} ai_objective:${objCol} ai_tools:${toolsCol} ai_topic:${topicCol}`,
  );

  const missing = [
    'title',
    'ai_objective',
    'ai_tools',
    'ai_topic',
  ].filter((h) => col(h) === -1);
  if (missing.length)
    throw new Error('Missing columns: ' + missing.join(', '));

  const apiKey =
    PropertiesService.getScriptProperties().getProperty(
      'GEMINI_API_KEY',
    );
  if (!apiKey)
    throw new Error(
      'Add GEMINI_API_KEY in Project Settings → Script Properties',
    );

  const data = sheet.getDataRange().getValues();
  Logger.log(`Total rows (incl. header): ${data.length}`);

  let eligible = 0;
  let updated = 0;

  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const hasTopic = row[topicCol] && row[topicCol].length >= 8;
    const hasObj = !!row[objCol];
    if (hasTopic || !hasObj) {
      Logger.log(
        `Row ${i + 1}: skipped (hasTopic=${hasTopic}, hasObj=${hasObj})`,
      );
      continue;
    }

    eligible++;
    const prompt = `Return ONLY a specific 2-5 word topic for this YouTube video. Be concrete, not categorical.
Good examples: "claude code + n8n", "shadcn table component", "RSI divergence strategy"
Bad examples: "coding tutorial", "market analysis"

Title: ${row[titleCol]}
Objective: ${row[objCol]}
Tools: ${row[toolsCol] || 'none'}`;

    try {
      const res = UrlFetchApp.fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`,
        {
          method: 'post',
          headers: { 'content-type': 'application/json' },
          payload: JSON.stringify({
            contents: [{ parts: [{ text: prompt }] }],
            generationConfig: { maxOutputTokens: 150 },
          }),
          muteHttpExceptions: true,
        },
      );

      const json = JSON.parse(res.getContentText());
      const topic =
        json?.candidates?.[0]?.content?.parts?.[0]?.text?.trim();
      Logger.log(
        `Row ${i + 1}: status=${res.getResponseCode()} topic="${topic}" raw=${JSON.stringify(json).slice(0, 300)}`,
      );

      if (topic) {
        sheet.getRange(i + 1, topicCol + 1).setValue(topic);
        updated++;
      }
    } catch (e) {
      Logger.log(`Row ${i + 1} failed: ${e.message}`);
    }

    Utilities.sleep(300);
  }

  const msg = `Done — ${updated}/${eligible} topics filled.`;
  Logger.log(msg);
  try {
    SpreadsheetApp.getUi().alert(msg);
  } catch (_) {}
}
