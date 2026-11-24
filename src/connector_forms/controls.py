"""Default form behavior shared by connectors."""


def find_row(rows, widget):
    return next((row for row in rows if widget in getattr(row, 'children', ())), None)


class FormControls:
    wide = False

    def __init__(self, form):
        self.form = form

    def skip_field(self, name):
        return False

    def widget(self, name, label, value):
        return None

    def rows(self):
        model = self.form.model
        pairs = getattr(model.support, 'FIELD_PAIRS', {})
        return self.form._field_rows((*pairs.get(None, ()), *pairs.get(model.action, ())))

    def after_render(self):
        pass

    def value_changed(self, name, value):
        pass

    def invalid_fields(self, fields):
        return fields

    def show_generation_error(self):
        return True

    def initial_directory(self, name):
        return None

    def close(self):
        pass
