"""Generate ordinary Python calls for local fulltext search."""
import ast
from pathlib import Path
from ...connector_codegen import _identifier, _integer, _text, module_name_for, render_call

BUILD = "fulltext_search.build_fulltext_db"
SEARCH = "fulltext_search.search_fulltext_db"
LEVENSHTEIN = "fulltext_search.search_levenshtein"
COMMON = {"db_folder","collection_name","output_variable"}
GENERATION_FIELDS = {
    BUILD: COMMON | {"input_variable","id_column","text_column","search_text_column","tokenizer"},
    SEARCH: COMMON | {"query_text","top_k"},
    LEVENSHTEIN: COMMON | {"query_text","max_distance","top_k"},
}
DEFAULT_PATHS = {"db_folder":"config/fulltext-db"}
RESET_DEFAULTS_ON_ACTION_CHANGE = ("output_variable",)

def generate(kind,values,module_path):
    if kind not in GENERATION_FIELDS:
        raise ValueError("Unknown Fulltext action")
    folder = Path(_text(values,"db_folder",required=True))
    if not folder.is_absolute():
        raise ValueError("DBフォルダーは絶対パスで指定してください。")
    params = {"db_folder":folder.as_posix(),
              "collection_name":_text(values,"collection_name",required=True)}
    if kind == BUILD:
        tokenizer = values.get("tokenizer","trigram")
        if tokenizer not in {"trigram","pretokenized"}:
            raise ValueError("Unknown tokenizer")
        params.update(id_column=_text(values,"id_column",required=True),
                      text_column=_text(values,"text_column",required=True),tokenizer=tokenizer)
        if values.get("search_text_column"):
            params["search_text_column"] = _text(values,"search_text_column",required=True)
    else:
        params.update(query_text=_text(values,"query_text",required=True),
                      top_k=_integer(values,"top_k",1))
        if kind == LEVENSHTEIN:
            params["max_distance"] = _integer(values, "max_distance", 0)
    args = [ast.keyword(arg=k,value=ast.Constant(v)) for k,v in params.items()]
    if kind == BUILD:
        args.append(ast.keyword(arg="input_data",value=ast.Name(id=_identifier(values,"input_variable"),ctx=ast.Load())))
    return render_call(module_name_for(module_path),kind.split(".",1)[1],args,
                       _identifier(values,"output_variable"),reading=True)
