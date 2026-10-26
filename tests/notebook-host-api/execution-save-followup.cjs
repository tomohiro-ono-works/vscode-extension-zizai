'use strict';
// Only gaps in D4 queued edit/save and D5 queued-close save; preserve old reports.
module.exports = { run: () => require('./execution-auto.cjs').run({
  d4: false, d4Queued: true, d5: ['D5-queued-close'],
  resultName: 'execution-save-followup-result.local.json',
  environmentCommand: 'notebook.execute', kernelTimeoutMs: 45000, automaticOnly: true
}) };
