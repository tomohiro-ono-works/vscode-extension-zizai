"use strict";
const fs = require('node:fs/promises');
const path = require('node:path');
const assert = require('node:assert/strict');

async function runDependentFlow({ page, editor, workspace, notebookFile, fixture, report, stage, externalYaml }) {
  const expected = (parent, child) => '%%ziz.connector.action.selector\nconnector.name = ' + JSON.stringify(parent) + ' # parent\nconnector.action.name = ' + JSON.stringify(child) + ' # child\nother = "keep"';
  async function visible(parent, child) {
    const text = expected(parent, child);
    let actual;
    for (let i = 0; i < 50; i++) {
      actual = (await editor.locator('.view-lines .view-line').allTextContents()).join('\n').replaceAll('\u00a0', ' ');
      if (actual === text) return;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    assert.equal(actual, text);
  }
  async function choose(markerLabel, value) {
    const marker = editor.locator('zizaiMarker=[' + markerLabel + ']');
    await marker.hover({ scroll: 'none' });
    const menu = page.locator('.monaco-hover').filter({ has: page.getByRole('link', { name: value, exact: true }) });
    const link = menu.getByRole('link', { name: value, exact: true });
    await link.waitFor({ state: 'visible', timeout: 10000 });
    const start = await marker.boundingBox(), end = await link.boundingBox();
    assert(start && end);
    const from = { x: start.x + start.width/2, y: start.y + start.height/2 };
    const to = { x: end.x + end.width/2, y: end.y + end.height/2 };
    const steps = Math.ceil(Math.hypot(to.x-from.x, to.y-from.y));
    const movement = { markerLabel, value, from, to, steps, startedAt:Date.now(), menu: await menu.boundingBox() };
    (report.dependentMovements ||= []).push(movement);
    for (let step=1; step<=steps; step++) {
      const point = { x:from.x + (to.x-from.x)*step/steps, y:from.y + (to.y-from.y)*step/steps };
      if (report.diagnosePointer) {
        const hit = await page.evaluate(point => {
          const hover = document.querySelector('.monaco-hover');
          const describe = e => e ? { tag:e.tagName, class:e.className,
            ancestors:[e.parentElement,e.parentElement?.parentElement].filter(Boolean).map(x=>x.className),
            inHover:!!hover?.contains(e) } : null;
          return { exact:describe(document.elementFromPoint(point.x,point.y)),
            rounded:describe(document.elementFromPoint(Math.round(point.x),Math.round(point.y))) };
        },point);
        (movement.hitTargets ||= []).push({step,point,hit});
      }
      await page.mouse.move(point.x,point.y);
      await new Promise(resolve => setTimeout(resolve, report.pointerStepDelayMs||8));
      if (!await link.isVisible()) { movement.disappearedAtStep = step; movement.disappearedAt=Date.now(); throw Error('Dependent hover disappeared during continuous movement'); }
    }
    await page.mouse.down(); await page.mouse.up();
    await menu.waitFor({ state: 'hidden', timeout: 5000 });
  }
  async function saved(parent, child) {
    await editor.locator('.view-lines').click();
    await page.keyboard.press('Control+s');
    let data;
    for (let i=0; i<50; i++) {
      data = JSON.parse(await fs.readFile(notebookFile, 'utf8'));
      if (data.cells[0].source.join('') === expected(parent,child)) break;
      await new Promise(resolve => setTimeout(resolve,100));
    }
    assert.equal(data.cells[0].source.join(''), expected(parent,child));
    assert.equal(data.cells.length,2);
    assert.deepEqual(data.cells[1],fixture.cells[1]);
    assert.deepEqual(data.cells[0].metadata,fixture.cells[0].metadata);
    assert.deepEqual(data.metadata,fixture.metadata);
    assert.deepEqual(data.cells[0].outputs,[]);
    assert.equal(data.cells[0].execution_count,null);
  }
  await choose('C','csv'); await visible('csv','');
  await choose('A','shared'); await visible('csv','shared');
  await choose('C','excel'); await visible('excel','shared');
  await stage('external_yaml_candidate_and_valid_child_preserved_without_save');
  await choose('A','excel_only'); await visible('excel','excel_only');
  await choose('C','csv'); await visible('csv','');
  await stage('invalid_child_cleared_with_parent_without_save');
  await saved('csv','');
  await page.keyboard.press('Control+z'); await saved('excel','excel_only');
  await page.keyboard.press('Control+y'); await saved('csv','');
  await stage('single_undo_restored_parent_and_child_redo_and_unrelated_cell_preserved');
  await fs.writeFile(path.join(workspace,'.vscode/zizai-definitions.yaml'),externalYaml.replace('csv: [shared, csv_only]','csv: [fresh]'));
  await choose('A','fresh'); await visible('csv','fresh'); await saved('csv','fresh');
  await stage('external_yaml_change_reloaded_without_restart');
  report.dependent = { externalYamlUsed: true, validChildPreserved: true, invalidChildCleared: true,
    singleUndoRestoredBoth: true, redo: true, unrelatedCellAndMetadataPreserved: true, reloadedOnChange: true };
}
module.exports = { runDependentFlow };
