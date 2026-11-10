"use strict";
const path = require("node:path");

// Pure source editing: no VS Code, filesystem, Python or kernel side effects.
function findSelections(source, definitions) {
  const lines = source.split("\n");
  const magic = /^%%([\w.]+)[ \t]*\r?$/.exec(lines[0]);
  const fields = magic && definitions.magics?.[magic[1]]?.fields;
  if (!fields) return [];

  const result = [];
  let offset = lines[0].length + 1;
  for (let line = 1; line < lines.length; line += 1) {
    for (const [field, definition] of Object.entries(fields)) {
      const escaped = field.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const pattern = new RegExp(
        "^([ \\t]*" + escaped + "[ \\t]*=[ \\t]*)(\"(?:[^\"\\\\\\r\\n]|\\\\.)*\")([ \\t]*(?:#.*)?\\r?)$"
      );
      const match = pattern.exec(lines[line]);
      const isPath = definition.kind === "file" || definition.kind === "folder";
      if (!match || (!isPath && !definition.dependsOn && (!Array.isArray(definition.choices) ||
          !definition.choices.every(value => typeof value === "string")))) continue;
      let current;
      try {
        current = JSON.parse(match[2]);
      } catch {
        // Unsupported Python literal syntax stays ordinary editable source.
        continue;
      }
      const character = match[1].length;
      result.push({
        magic: magic[1], field, label: definition.label,
        kind: isPath ? definition.kind : "choice",
        dependsOn: definition.dependsOn,
        choices: isPath || definition.dependsOn ? [] : [...definition.choices], current, line, character,
        start: offset + character, end: offset + character + match[2].length,
        original: match[2]
      });
    }
    offset += lines[line].length + 1;
  }
  function choicesFor(item, visiting = new Set()) {
    if (!item.dependsOn) return item.choices;
    if (visiting.has(item.field)) return [];
    const next = new Set(visiting).add(item.field);
    const parents = result.filter(parent => parent.field === item.dependsOn);
    if (parents.length !== 1 || !parents[0].current || !choicesFor(parents[0], next).includes(parents[0].current)) return [];
    const definition = fields[item.field];
    return Object.hasOwn(definition.choicesByValue, parents[0].current)
      ? definition.choicesByValue[parents[0].current] : [];
  }
  for (const item of result) if (item.dependsOn) item.choices = [...choicesFor(item)];
  return result;
}

function planChoiceEdits(source, selection, value, definitions) {
  if (replaceChoice(source, selection, value) === source) return [];
  const original = findSelections(source, definitions);
  if (original.filter(item => item.field === selection.field).length !== 1) return [];
  const edits = [{ start: selection.start, end: selection.end, text: JSON.stringify(value) }];
  const affected = new Set([selection.field]);
  for (let pass = 0; pass < original.length; pass += 1) {
    let next = source;
    for (const edit of [...edits].sort((a, b) => b.start - a.start)) next = next.slice(0, edit.start) + edit.text + next.slice(edit.end);
    const current = findSelections(next, definitions);
    let added = false;
    for (const child of original) {
      if (!child.dependsOn || !affected.has(child.dependsOn) || affected.has(child.field)) continue;
      if (original.filter(item => item.field === child.field).length !== 1) continue;
      const updated = current.find(item => item.field === child.field);
      if (child.current !== '' && updated && !updated.choices.includes(child.current)) {
        edits.push({ start: child.start, end: child.end, text: '""' });
        affected.add(child.field);
        added = true;
      }
    }
    if (!added) break;
  }
  return edits;
}

function replaceChoice(source, selection, value) {
  if (!selection.choices.includes(value)) return source;
  return replaceLiteral(source, selection, value);
}

function replacePath(source, selection, value) {
  if (!["file", "folder"].includes(selection.kind) || typeof value !== "string" || !path.isAbsolute(value)) return source;
  return replaceLiteral(source, selection, value);
}

function replaceLiteral(source, selection, value) {
  if (typeof value !== "string" ||
      source.slice(selection.start, selection.end) !== selection.original) return source;
  return source.slice(0, selection.start) + JSON.stringify(value) + source.slice(selection.end);
}

module.exports = { findSelections, replaceChoice, replacePath, planChoiceEdits };
