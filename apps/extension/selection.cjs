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
      if (!match || (!isPath && (!Array.isArray(definition.choices) ||
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
        choices: isPath ? [] : [...definition.choices], current, line, character,
        start: offset + character, end: offset + character + match[2].length,
        original: match[2]
      });
    }
    offset += lines[line].length + 1;
  }
  return result;
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

module.exports = { findSelections, replaceChoice, replacePath };
