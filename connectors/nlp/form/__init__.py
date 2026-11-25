"""Generate notebook calls without executing NLP or evaluating user input."""
import ast
from ...connector_codegen import _identifier, module_name_for, render_call

COMMON = {"input_mode","text","input_variable","text_column","id_column","output_variable"}
GENERATION_FIELDS = {
    "nlp.normalize_text": COMMON | {"form","collapse_whitespace","lowercase"},
    "nlp.analyze_text": COMMON | {"model","enable_coreference","resolver_variable"},
    "nlp.analyze_keyword_importance": COMMON | {"method","model","corpus_variable","embedding_model"},
}

def generate(kind, values, module_path):
    if kind not in GENERATION_FIELDS:
        raise ValueError("Unknown NLP action")
    action = kind.split(".")[1]
    args = []
    def constant(key, value):
        args.append(ast.keyword(arg=key,value=ast.Constant(value)))
    def variable(key, field):
        args.append(ast.keyword(arg=key,value=ast.Name(id=_identifier(values,field),ctx=ast.Load())))
    def boolean(key, default):
        value = values.get(key,default)
        if not isinstance(value,bool):
            raise ValueError(key+" must be boolean")
        constant(key,value)
    if values["input_mode"] == "dataframe":
        variable("data","input_variable")
        constant("text_column",values["text_column"])
        if values.get("id_column"):
            constant("id_column",values["id_column"])
    elif values["input_mode"] == "text":
        constant("data",values["text"])
    else:
        raise ValueError("Unknown input mode")
    if action == "normalize_text":
        form = values.get("form","NFKC")
        if form not in {"NFC","NFD","NFKC","NFKD"}:
            raise ValueError("Unknown Unicode normalization form")
        constant("form",form)
        boolean("collapse_whitespace",True)
        boolean("lowercase",False)
    else:
        constant("model",values.get("model") or "ja_ginza")
    if action == "analyze_text":
        boolean("enable_coreference",True)
        if values.get("enable_coreference",True) and values.get("resolver_variable"):
            variable("resolver","resolver_variable")
    if action == "analyze_keyword_importance":
        method = values.get("method")
        if method not in {"tfidf","textrank","keybert"}:
            raise ValueError("Select method")
        constant("method",method)
        if method == "keybert" and values.get("embedding_model"):
            constant("embedding_model",values["embedding_model"])
        if method == "tfidf" and values.get("corpus_variable"):
            variable("corpus","corpus_variable")
    return render_call(module_name_for(module_path),action,args,_identifier(values,"output_variable"),reading=True)
