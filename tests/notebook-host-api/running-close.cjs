'use strict';
module.exports = { run: () => require('./execution-auto.cjs').run({ d4: false, d5: ['D5-running-close'], environmentCommand: 'notebook.execute' }) };
