'use strict';
// D1 control: standard nbformat cell.id present; diagnostic metadata unchanged.
module.exports = { run: () => require('./structure.cjs').run(['delete'], { cellIds: true }) };
