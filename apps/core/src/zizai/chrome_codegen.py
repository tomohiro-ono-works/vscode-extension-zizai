"""Generate a standard Chrome connector call."""
import ast

from .connector_codegen import _identifier, _text, module_name_for, render_call


GENERATION_FIELDS = {'chrome.open_in_chrome': {'url', 'output_variable'}}


def generate_chrome(kind, values, module_path):
    if kind not in GENERATION_FIELDS:
        raise ValueError('未対応のChrome操作です。')
    module = module_name_for(module_path)
    variable = _identifier(values, 'output_variable')
    url = _text(values, 'url', required=True).strip()
    args = [ast.keyword(arg='url', value=ast.Constant(url))]
    return render_call(module, 'open_in_chrome', args, variable, reading=True)
