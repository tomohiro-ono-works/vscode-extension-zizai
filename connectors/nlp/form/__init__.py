"""Generate notebook calls without executing NLP or evaluating user input."""
import ast
from ...connector_codegen import _identifier, module_name_for, render_call

ACTIONS = ("normalize_text","tokenize","parse_dependencies","extract_entities",
           "extract_keywords","resolve_coreferences","split_sentences","split_bunsetsu")
COMMON = {"input_mode","text","input_variable","text_column","id_column","output_variable"}
GENERATION_FIELDS = {}
for action in ACTIONS:
    fields = set(COMMON)
    if action not in ("normalize_text","resolve_coreferences"): fields.add("model")
    if action == "extract_keywords": fields.update(("method","top_n","corpus_variable","embedding_model"))
    if action == "resolve_coreferences": fields.add("resolver_variable")
    GENERATION_FIELDS["nlp."+action] = fields

def generate(kind, values, module_path):
    if kind not in GENERATION_FIELDS: raise ValueError("Unknown NLP action")
    action = kind.split(".")[1]
    args = []
    def constant(key, value):
        args.append(ast.keyword(arg=key,value=ast.Constant(value)))
    def variable(key, field):
        args.append(ast.keyword(arg=key,value=ast.Name(id=_identifier(values,field),ctx=ast.Load())))
    if values["input_mode"] == "dataframe":
        variable("data","input_variable")
        constant("text_column",values["text_column"])
        if values.get("id_column"): constant("id_column",values["id_column"])
    elif values["input_mode"] == "text":
        constant("data",values["text"])
    else: raise ValueError("Unknown input mode")
    if "model" in GENERATION_FIELDS[kind]: constant("model",values["model"])
    if action == "extract_keywords":
        if values.get("method") not in ("tfidf","textrank","keybert"): raise ValueError("Select method")
        constant("method",values["method"])
        if values["method"] == "keybert" and values.get("embedding_model"):
            constant("embedding_model",values["embedding_model"])
        constant("top_n",int(values["top_n"]) or None)
        if values.get("corpus_variable"): variable("corpus","corpus_variable")
    if action == "resolve_coreferences" and values.get("resolver_variable"): variable("resolver","resolver_variable")
    return render_call(module_name_for(module_path),action,args,_identifier(values,"output_variable"),reading=True)
