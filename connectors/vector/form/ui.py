"""Vector collection, model and batch-query controls."""
from ...connector_forms.controls import FormControls
from .collection_names import _vector_collection_names
from .vector_codegen import BUILD, CORRECTION_FIELDS, SEARCH


class Controls(FormControls):
    @property
    def generation(self):
        return self.form.model.generation

    def skip_field(self, name):
        return self.generation == SEARCH and name == 'include_vector'

    def widget(self, name, label, value):
        form = self.form
        widgets = form._widgets
        if self.generation == SEARCH:
            if name == 'collection_name':
                return self._vector_collection_picker(form.model.values['db_folder'], label)
            if name == 'batch_search':
                widget = widgets.ToggleButtons(options=[('検索文', False), ('DataFrameで検索', True)],
                                               value=value, style={'button_width': 'auto'})
                widget.add_class('zizai-batch-toggle')
                return widget
            if name == 'query_column':
                return self._vector_column_picker(name, label, source_field='query_input_variable')
            if name == 'query_input_variable':
                return form._dataframe_picker(name, label)
        if self.generation == BUILD:
            if name in ('id_column', 'text_column'):
                return self._vector_column_picker(name, label)
            if name == 'input_variable':
                return form._dataframe_picker(name, label)
            if name == 'model_name':
                return form._choice_picker(name, label, value, placeholder='既存DBのモデルを使用（新規は130m）')
        return None

    def rows(self):
        form = self.form
        widgets = form._widgets
        fields = form.field_widgets
        if self.generation == SEARCH:
            rows = form._field_rows((('collection_name', 'search_mode'), ('output_variable', 'top_k'),
                                     ('query_input_variable', 'query_column')))
            toggle = fields.get('batch_search')
            if toggle is not None:
                query = fields['query_text']
                rows.remove(toggle)
                toggle.layout.align_self = 'flex-start'
                query.add_class('zizai-query-text')
                query.layout.width = '100%'
                section = widgets.VBox([toggle, query])
                section.add_class('zizai-query-section')
                form._dynamic.append(section)
                rows[rows.index(query)] = section
            return rows
        if self.generation == BUILD:
            rows = form._field_rows((('input_variable', 'output_variable'), ('id_column', 'text_column')))
            controls = [field for name, field in fields.items() if name in CORRECTION_FIELDS]
            if controls:
                for field in controls:
                    rows.remove(field)
                settings = widgets.VBox(controls)
                advanced = widgets.Accordion(children=[settings], selected_index=None)
                advanced.set_title(0, '補正検索の詳細設定')
                form._dynamic.extend([settings, advanced])
                rows.append(advanced)
            return rows
        return super().rows()

    def after_render(self):
        if self.generation == SEARCH and 'batch_search' in self.form.field_widgets:
            self._show_vector_query_mode()

    def value_changed(self, name, value):
        fields = self.form.field_widgets
        if self.generation == SEARCH:
            if name == 'db_folder':
                label = fields['collection_name'].description
                self._replace_vector_picker('collection_name', self._vector_collection_picker(value, label))
            elif name == 'batch_search':
                self._show_vector_query_mode()
            elif name == 'query_input_variable':
                label = fields['query_column'].description
                picker = self._vector_column_picker('query_column', label, source_field=name)
                self._replace_vector_picker('query_column', picker)
        if self.generation == BUILD and name == 'input_variable':
            for column in ('id_column', 'text_column'):
                self._replace_vector_picker(column, self._vector_column_picker(column, fields[column].description))

    def _show_vector_query_mode(self):
        batch = self.form.model.values['batch_search']
        fields = self.form.field_widgets
        fields['query_text'].layout.display = 'none' if batch else ''
        row = next(row for row in self.form.details.children
                   if fields['query_input_variable'] in getattr(row, 'children', ()))
        row.layout.display = '' if batch else 'none'

    def _vector_collection_picker(self, folder, label):
        names = _vector_collection_names(folder)
        current = self.form.model.values['collection_name']
        selected = current if current in names else (names[0] if len(names) == 1 else '')
        self.form.model.set_value('collection_name', selected)
        placeholder = ('選択してください' if names else
                       'コレクションがありません' if folder else 'フォルダーを選択してください')
        options = [(placeholder, ''), *((name, name) for name in names)]
        picker = self.form._widgets.Dropdown(description=label, options=options, value=selected, disabled=not names,
                                        description_allow_html=True)
        picker.style.description_width = 'initial'
        return picker

    def _vector_column_picker(self, name, label, *, source_field='input_variable'):
        source = self.form.model.values.get(source_field)
        data = self.form._namespace.get(source)
        labels = getattr(data, 'columns', None)
        if labels is None:
            labels = ()
        elif name == 'query_column':
            labels = labels[~labels.duplicated(keep=False)]
        columns = tuple(dict.fromkeys(column for column in labels
                                      if isinstance(column, str) and column.strip()))
        selected = self.form.model.values[name]
        if selected not in columns:
            default = self.form.model.fields[name].get('default')
            selected = default if default in columns else ''
        self.form.model.set_value(name, selected)
        placeholder = ('選択してください' if columns else
                       '選択できる列がありません' if source else '入力DataFrameを選択してください')
        options = [(placeholder, ''), *((column, column) for column in columns)]
        picker = self.form._widgets.Dropdown(description=label, options=options, value=selected, disabled=not columns,
                                        description_allow_html=True)
        picker.style.description_width = 'initial'
        return picker

    def _replace_vector_picker(self, name, picker):
        previous = self.form.field_widgets[name]
        picker.layout = previous.layout
        picker.observe(lambda change: self.form._value_changed(name, change['new']), names='value')
        row = next(row for row in self.form.details.children if previous in getattr(row, 'children', ()))
        row.children = tuple(picker if item is previous else item for item in row.children)
        self.form.field_widgets[name] = picker
        self.form._dynamic[self.form._dynamic.index(previous)] = picker
        previous.unobserve_all('value')
        previous.close()
