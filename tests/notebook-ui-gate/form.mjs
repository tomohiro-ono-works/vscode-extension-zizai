// Deliberately tiny fake connector UI, shared by the two experimental surfaces.
// It neither generates nor runs Python. Values exist only in the probe's memory.
export function mountForm(root, initial, changed) {
  const label = document.createElement('label');
  label.textContent = '選択（試作） ';
  const select = document.createElement('select');
  select.setAttribute('aria-label', '選択（試作）');
  for (const [value, text] of [['python', '通常Python'], ['fake', '架空コネクタ / 入力テスト']]) {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = text;
    select.append(option);
  }
  select.value = initial.mode === 'fake' ? 'fake' : 'python';
  label.append(select);
  const details = document.createElement('div');
  const inputLabel = document.createElement('label');
  inputLabel.textContent = 'テスト値（実データを入力しない） ';
  const input = document.createElement('input');
  input.setAttribute('aria-label', 'テスト値');
  input.value = typeof initial.value === 'string' ? initial.value : '';
  input.maxLength = 120;
  inputLabel.append(input);
  details.append(inputLabel);
  root.append(label, details);
  const update = () => {
    details.hidden = select.value !== 'fake';
    changed({ mode: select.value, value: input.value });
  };
  select.addEventListener('change', update);
  input.addEventListener('input', update);
  details.hidden = select.value !== 'fake';
}
