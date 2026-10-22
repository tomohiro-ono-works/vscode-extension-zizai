import { mountForm } from './form.mjs';

export function activate() {
  return {
    renderOutputItem(outputItem, element) {
      element.replaceChildren();
      const note = document.createElement('p');
      note.textContent = '対照実験: 保存済みOUTPUT内のフォーム。実行前常設の合格証拠には使わない。';
      element.append(note);
      mountForm(element, outputItem.json(), () => {});
    }
  };
}
