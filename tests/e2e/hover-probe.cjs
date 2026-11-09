"use strict";
const assert = require('node:assert/strict');

// Bounded diagnosis of the previously failed continuous pointer transition.
// No retry after disappearance, delay before movement, synthetic events, or product patch.
async function runHoverProbe({ page, editor, report, stage, automaticScroll = false }) {
  report.hoverProbe = { attempts: [], limit: 8, stepDelayMs: 8, clickPerformed: false, automaticScroll };
  const layout = async marker => ({ marker: await marker.boundingBox(), viewLines: await editor.locator('.view-lines').boundingBox(),
    scroll: await editor.evaluate(e => [...e.querySelectorAll('*')].filter(x => x.scrollLeft).map(x => ({ class:x.className, left:x.scrollLeft }))) });
  for (let index = 0; index < 8; index++) {
    const kind = index % 2 === 0 ? 'file' : 'folder';
    const attempt = { index, kind };
    report.hoverProbe.attempts.push(attempt);
    const marker = editor.locator('zizaiMarker=[P]').nth(index % 2);
    if (index) {
      await page.keyboard.press('Escape');
      const box = await editor.boundingBox();
      await page.mouse.move(box.x + box.width - 10, box.y + box.height - 8);
    }
    attempt.beforeHover = await layout(marker);
    await marker.hover({ scroll: automaticScroll ? 'auto' : 'none' });
    attempt.afterHover = await layout(marker);
    const name = kind === 'file' ? 'ファイルを選択' : 'フォルダーを選択';
    const hover = page.locator('.monaco-hover').filter({ has: page.getByRole('link', { name, exact: true }) });
    const link = hover.getByRole('link', { name, exact: true });
    await link.waitFor({ state: 'visible', timeout: 10000 });
    const start = await marker.boundingBox(), target = await link.boundingBox();
    assert(start && target);
    const from = { x: start.x + start.width/2, y: start.y + start.height/2 };
    const to = { x: target.x + target.width/2, y: target.y + target.height/2 };
    const steps = Math.ceil(Math.hypot(to.x-from.x, to.y-from.y));
    Object.assign(attempt, { from, to, steps, marker:start, target, menu:await hover.boundingBox() });
    for (let step=1; step<=steps; step++) {
      const point = { x:from.x+(to.x-from.x)*step/steps, y:from.y+(to.y-from.y)*step/steps };
      await page.mouse.move(point.x,point.y);
      await new Promise(resolve => setTimeout(resolve,8));
      if (!await link.isVisible()) {
        attempt.disappearedAtStep = step;
        attempt.point = point;
        attempt.currentMarker = await marker.boundingBox();
        attempt.visibleHovers = await page.locator('.monaco-hover').evaluateAll(elements => elements.map(e => ({ text:e.textContent, bounds:e.getBoundingClientRect().toJSON(), display:getComputedStyle(e).display })));
        attempt.hoveredElements = await page.locator(':hover').evaluateAll(elements => elements.map(e => ({ tag:e.tagName, class:e.className, bounds:e.getBoundingClientRect().toJSON() })).slice(-12));
        await stage('hover_probe_disappeared_without_retry');
        throw Error('Path hover disappeared at attempt ' + index + ', step ' + step + '/' + steps);
      }
    }
    const final = await link.boundingBox();
    attempt.finalTarget = final;
    assert(final && to.x>=final.x && to.x<=final.x+final.width && to.y>=final.y && to.y<=final.y+final.height, 'Pointer must reach the actual candidate');
    attempt.reached = true;
    await stage('hover_probe_' + index + '_' + kind + '_reached');
  }
}
module.exports = { runHoverProbe };
