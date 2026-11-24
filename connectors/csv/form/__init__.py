"""Form support for the csv connector."""
from . import preview as ROW_PREVIEW
from .csv_codegen import GENERATION_FIELDS, generate_csv as generate

FILE_PATH_GENERATIONS = ('csv.read_csv',)

MAGIC_NAME = 'zizai_csv'

OUTPUT_SUFFIX = '.csv'

ROW_PREVIEW_FIELDS = {'import': {'encoding': 'choice', 'delimiter': 'text'}}
FIELD_PAIRS = {None: (('encoding', 'delimiter'),),
               'import': (('output_variable', 'chunk_size'), ('header_row', 'data_start_row'))}
