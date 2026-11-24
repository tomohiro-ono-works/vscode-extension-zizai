"""Form support for the excel connector."""
from . import preview as ROW_PREVIEW
from .excel_codegen import GENERATION_FIELDS, generate_excel as generate

FILE_PATH_GENERATIONS = ('excel.read_excel', 'excel.read_excel_range')

MAGIC_NAME = 'zizai_excel'

OUTPUT_SUFFIX = '.xlsx'

ROW_PREVIEW_FIELDS = {'read_excel': {'sheet_name': 'text'}}
READ_PAIRS = (('output_variable', 'chunk_size'), ('header_row', 'data_start_row'))
FIELD_PAIRS = {'read_excel': READ_PAIRS, 'read_excel_range': READ_PAIRS}
