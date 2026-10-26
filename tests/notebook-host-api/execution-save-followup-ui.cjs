'use strict';
// Same two conditions after the user selects/runs the standard Python kernel.
module.exports = { run: () => require('./execution-auto.cjs').run({
  d4: false, d4Queued: true, d5: ['D5-queued-close'],
  resultName: 'execution-save-followup-result.local.json',
  environmentCommand: 'notebook.execute', kernelTimeoutMs: null
}) };
