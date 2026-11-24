"""Coordinate capture and wait controls for Windows actions."""
from asyncio import get_running_loop

from ...connector_forms.controls import FormControls, find_row
from .cursor import _read_cursor_position


class Controls(FormControls):
    def __init__(self, form):
        super().__init__(form)
        self._cursor_capture_timer = None
        self.cursor_capture_button = None

    def rows(self):
        form = self.form
        rows = form._field_rows((('wait_before_seconds', 'wait_after_seconds'), ('x', 'y')))
        if form.model.generation == 'windows.mouse_click' and {'x', 'y'} <= form.field_widgets.keys():
            row = find_row(rows, form.field_widgets['x'])
            widgets = form._widgets
            button = widgets.Button(description='3秒後に座標取得',
                                    layout=widgets.Layout(width='auto', flex='0 0 auto', align_self='flex-end'))
            button.on_click(self._schedule_cursor_capture)
            self.cursor_capture_button = button
            form._dynamic.append(button)
            row.children = (*row.children, button)
        return rows

    def _schedule_cursor_capture(self, button):
        if button is not self.cursor_capture_button or self._cursor_capture_timer is not None:
            return
        try:
            self._cursor_capture_timer = get_running_loop().call_later(3, self._capture_cursor, button)
        except RuntimeError:
            self.form.message.value = '座標取得にはNotebookのカーネルが必要です。'
            return
        button.disabled = True
        button.description = '取得中…'
        self.form.message.value = '取得したい位置にマウスを移動してください。'

    def _capture_cursor(self, button):
        if button is not self.cursor_capture_button or self._cursor_capture_timer is None:
            return
        self._cursor_capture_timer = None
        button.description = '3秒後に座標取得'
        button.disabled = False
        try:
            x, y = _read_cursor_position()
        except OSError:
            self.form.message.value = '座標を取得できません。ローカルWindowsの画面で試してください。'
            return
        self.form.field_widgets['x'].value = str(x)
        self.form.field_widgets['y'].value = str(y)
        self.form.field_widgets['coordinate_mode'].value = '座標指定'
        self.form.message.value = f'座標を取得しました。X = {x}、Y = {y}'

    def close(self):
        if self._cursor_capture_timer is not None:
            self._cursor_capture_timer.cancel()
            self._cursor_capture_timer = None
