import ast
from ...connector_codegen import _identifier, _text, absolute_file_path, module_name_for, render_call

ACTION_FIELDS = {"create_graph":[],"add_triples":["input_variable"],"remove_triples":["input_variable"],"search_graph":["sparql"],"define_class":["class_uri","label","parent_uri"],"define_property":["property_uri","domain_uri","range_uri","property_type","label"],"search_ontology":["sparql"],"list_ancestors":["class_uri"],"infer_types":[],"validate_ontology":[]}
GENERATION_FIELDS = {"knowledge."+name: set(fields)|{"db_file","output_variable"} for name,fields in ACTION_FIELDS.items()}

def generate(kind, values, module_path):
    if kind not in GENERATION_FIELDS:
        raise ValueError("未対応のKnowledge生成種別です。")
    action = kind.split(".",1)[1]
    args = [ast.keyword(arg="db_file", value=ast.Constant(absolute_file_path(values,"db_file")))]
    for field in ACTION_FIELDS[action]:
        if field == "input_variable":
            args.append(ast.keyword(arg="df",value=ast.Name(id=_identifier(values,field),ctx=ast.Load())))
        else:
            optional = field in {"label","parent_uri","domain_uri","range_uri"}
            value = _text(values,field,required=not optional)
            args.append(ast.keyword(arg=field,value=ast.Constant(value or None)))
    return render_call(module_name_for(module_path),action,args,_identifier(values,"output_variable"),reading=True)
