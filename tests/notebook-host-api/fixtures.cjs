'use strict';
const metadata = label => ({ outsideDiagnosticOwner: { sentinel: 'keep-' + label }, task00201Diagnostic: { label, draft: 0, committed: 0, burst: 0, probeOnly: true } });
function cell(label, source) {
  return { cell_type: 'code', execution_count: null, metadata: metadata(label), outputs: [], source: source.split(/(?<=\n)/) };
}
const env = `import sys, importlib.metadata as m, json\nprint(json.dumps({'python': sys.version, 'ipykernel': m.version('ipykernel'), 'jupyter_client': m.version('jupyter_client')}, indent=2))\n`;
const wait = label => `import time\nprint('${label} started', flush=True)\ntime.sleep(90)\nprint('${label} finished', flush=True)\n`;
const cases = {
  'D1-structure': [cell('A', '# D1-A: move this cell\nvalue_a = 101\n'), cell('B', '# D1-B\nvalue_b = 202\n'), cell('C', '# D1-C\nvalue_c = 303\n')],
  'D2-save': [cell('D2', '# D2: metadata-only must preserve this source\nfictional_value = 42\n')],
  'D3-mixed': [cell('D3', '# D3 baseline\nfictional_value = 10\n')],
  'D4-environment': [cell('environment', env)],
  'D4-success': [cell('success', "print('diagnostic success')\n")],
  'D4-exception': [cell('exception', "raise ValueError('fictional diagnostic exception')\n")],
  'D4-cancel': [cell('cancel', wait('cancel'))],
  'D4-empty': [cell('empty', '')],
  'D4-running-edit': [cell('running-edit', wait('running-edit'))],
  'D4-nonempty-to-empty': [cell('nonempty-to-empty', wait('nonempty-to-empty'))],
  'D4-queued-edit': [cell('blocker', wait('blocker')), cell('queued', "print('queued ORIGINAL')\n")],
  'D5-queued-delete': [cell('blocker', wait('D5 blocker')), cell('queued', "print('D5 queued original')\n")],
  'D5-running-delete': [cell('running', wait('D5 running')), cell('observer', "print('D5 kernel still responds')\n")],
  'D5-queued-close': [cell('blocker', wait('D5 blocker')), cell('queued', "print('D5 queued original')\n")],
  'D5-running-close': [cell('running', wait('D5 running'))],
  'D6-burst': [cell('D6-existing', '# D6 existing cell\nfictional_value = 60\n')]
};
function notebook(name) {
  if (!Object.hasOwn(cases, name)) throw new Error('Unknown diagnostic case');
  return { cells: structuredClone(cases[name]), metadata: { kernelspec: { display_name: 'Python 3 (ipykernel)', language: 'python', name: 'python3' }, language_info: { name: 'python' }, task00201Diagnostic: { probeOnly: true, case: name }, outsideNotebookOwner: { sentinel: 'preserve-notebook' } }, nbformat: 4, nbformat_minor: 5 };
}
module.exports = { cases, notebook };
