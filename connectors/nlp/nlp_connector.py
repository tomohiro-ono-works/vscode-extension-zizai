"""Japanese NLP operations with DataFrame outputs."""
from functools import lru_cache
from numbers import Integral
from uuid import UUID, NAMESPACE_URL, uuid4, uuid5
import json
import unicodedata
import pandas as pd

def _docs(data, text_column="text", id_column=None):
    if isinstance(data, str):
        return [(1, data)]
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be str or DataFrame")
    ids = data[id_column] if id_column else range(1, len(data)+1)
    if id_column and (data[id_column].isna().any() or data[id_column].duplicated().any()):
        raise ValueError("Document IDs must be unique and non-null")
    result = list(zip(ids, data[text_column]))
    if any(not isinstance(t, str) for _, t in result):
        raise TypeError("Text values must be strings")
    return result

@lru_cache(maxsize=2)
def _model(model):
    import spacy
    return spacy.load(model)

def _parsed(data, text_column, id_column, model):
    docs = _docs(data, text_column, id_column)
    return zip((i for i,t in docs), _model(model).pipe(t for i,t in docs))

def normalize_text(data, *, text_column="text", id_column=None, form="NFKC", collapse_whitespace=True, lowercase=False):
    rows = []
    for i,t in _docs(data,text_column,id_column):
        s = unicodedata.normalize(form,t)
        if collapse_whitespace: s = " ".join(s.split())
        if lowercase: s = s.lower()
        rows.append((i,t,s))
    return pd.DataFrame(rows,columns=["doc_id","original_text","normalized_text"])

def _tokens(data,text_column,id_column,model,dependencies):
    columns = ["doc_id","token_id","text","lemma","pos","start","end","morph"]
    if dependencies: columns += ["head_id","dependency"]
    rows = []
    for i,d in _parsed(data,text_column,id_column,model):
        for t in d:
            row = [i,t.i,t.text,t.lemma_,t.pos_,t.idx,t.idx+len(t.text),str(t.morph)]
            if dependencies: row += [t.head.i,t.dep_]
            rows.append(row)
    return pd.DataFrame(rows,columns=columns)

def tokenize(data, *, text_column="text", id_column=None, model="ja_ginza"):
    return _tokens(data,text_column,id_column,model,False)

def parse_dependencies(data, *, text_column="text", id_column=None, model="ja_ginza"):
    return _tokens(data,text_column,id_column,model,True)

def extract_entities(data, *, text_column="text", id_column=None, model="ja_ginza"):
    return pd.DataFrame([(i,j,e.text,e.label_,e.start_char,e.end_char)
        for i,d in _parsed(data,text_column,id_column,model) for j,e in enumerate(d.ents)],
        columns=["doc_id","entity_id","text","label","start","end"])

def split_sentences(data, *, text_column="text", id_column=None, model="ja_ginza"):
    return pd.DataFrame([(i,j,s.text,s.start_char,s.end_char)
        for i,d in _parsed(data,text_column,id_column,model) for j,s in enumerate(d.sents)],
        columns=["doc_id","sentence_id","text","start","end"])

def split_bunsetsu(data, *, text_column="text", id_column=None, model="ja_ginza"):
    import ginza
    return pd.DataFrame([(i,j,s.text,s.start_char,s.end_char)
        for i,d in _parsed(data,text_column,id_column,model) for j,s in enumerate(ginza.bunsetu_spans(d))],
        columns=["doc_id","bunsetsu_id","text","start","end"])

def extract_keywords(data, *, method, text_column="text", id_column=None, model="ja_ginza", top_n=None, corpus=None, embedding_model="cl-nagoya/ruri-v3-130m"):
    if method not in {"tfidf","textrank","keybert"}:
        raise ValueError("Unknown keyword method")
    if top_n is not None and top_n < 1: raise ValueError("top_n must be positive")
    docs = list(_parsed(data,text_column,id_column,model))
    def terms(d):
        return [t.lemma_ for t in d if t.pos_ in {"NOUN","PROPN","VERB","ADJ"} and not t.is_stop]
    lists = [terms(d) for _,d in docs]
    scores = []
    if method == "tfidf":
        from sklearn.feature_extraction.text import TfidfVectorizer
        reference = [_model(model)(t) for t in corpus] if corpus is not None else [d for _,d in docs]
        if len(reference)<2: raise ValueError("TF-IDF requires a reference corpus of at least two documents")
        v = TfidfVectorizer(analyzer=lambda x:x)
        training = [terms(d) for d in reference]
        if any(training):
            v.fit(training)
            matrix = v.transform(lists) if lists else []
            names = v.get_feature_names_out()
            for ts,row in zip(lists,matrix):
                score = dict.fromkeys(ts,0.0)
                score.update({names[j]:float(x) for j,x in zip(row.indices,row.data)})
                scores.append(score)
        else: scores = [dict.fromkeys(ts,0.0) for ts in lists]
    elif method == "textrank":
        import networkx as nx
        for ts in lists:
            g = nx.Graph()
            g.add_nodes_from(ts)
            for j,a in enumerate(ts):
                for b in ts[j+1:j+4]:
                    if a != b: g.add_edge(a,b,weight=g.get_edge_data(a,b,{}).get("weight",0)+1)
            scores.append(nx.pagerank(g,weight="weight") if g else {})
    else:
        from keybert import KeyBERT
        from sentence_transformers import SentenceTransformer
        encoder = KeyBERT(model=SentenceTransformer(
            embedding_model, device="cpu", trust_remote_code=False, local_files_only=True,
            model_kwargs={"use_safetensors": True},
            revision="e3114c6ee10dbab8b4b235fbc6dcf9dd4d5ac1a6"
            if embedding_model == "cl-nagoya/ruri-v3-130m" else None))
        for (_,d),ts in zip(docs,lists):
            candidates = list(dict.fromkeys(ts))
            if not candidates:
                scores.append({}); continue
            # Use the same morphological representation for candidates and document.
            from sklearn.feature_extraction.text import CountVectorizer
            vectorizer = CountVectorizer(vocabulary=candidates, tokenizer=str.split,
                                         token_pattern=None, lowercase=False)
            # Supply embeddings of the original document to retain its context.
            doc_embeddings = encoder.model.embed([d.text])
            word_embeddings = encoder.model.embed(candidates)
            scores.append(dict(encoder.extract_keywords(" ".join(ts),
                vectorizer=vectorizer, top_n=len(candidates),
                doc_embeddings=doc_embeddings, word_embeddings=word_embeddings)))
    rows = []
    for (i,_),score in zip(docs,scores):
        for rank,(word,value) in enumerate(sorted(score.items(),key=lambda x:(-x[1],x[0]))[:top_n],1):
            rows.append((i,word,value,rank,method))
    return pd.DataFrame(rows,columns=["doc_id","keyword","score","rank","method"])

def resolve_coreferences(data, *, text_column="text", id_column=None, resolver=None):
    """Use an explicitly supplied Japanese coreference resolver returning span dictionaries."""
    if resolver is None:
        resolver = _heuristic_coreferences
    columns = ["doc_id","mention","antecedent","antecedent_start","antecedent_end"]
    rows = []
    for i,t in _docs(data,text_column,id_column):
        for item in resolver(t):
            rows.append([i,*[item[k] for k in columns[1:]]])
    return pd.DataFrame(rows,columns=columns)

def _heuristic_coreferences(text):
    return _heuristic_coreferences_doc(_model("ja_ginza")(text))

def _heuristic_coreferences_doc(doc):
    """Conservative baseline: explicit third-person pronouns and preceding person entities.
    This is not a general Japanese coreference model; ambiguous candidates are skipped.
    """
    for token in doc:
        if token.pos_ != "PRON" or token.text not in {"彼","彼女","彼ら"}:
            continue
        candidates = [e for e in doc.ents if e.end <= token.i and e.label_ in {"Person","PERSON"}]
        unique = {e.text:e for e in candidates}
        if len(unique) != 1 or token.text == "彼ら":
            continue
        e = next(iter(unique.values()))
        yield {"mention":token.text,"mention_start":token.idx,
               "mention_end":token.idx+len(token.text),"antecedent":e.text,
               "antecedent_start":e.start_char,"antecedent_end":e.end_char}


# Public consolidated analysis API. Legacy functions remain available to
# existing notebooks; only the consolidated actions are exposed in the form.
ANALYSIS_COLUMNS = [
    "doc_id", "sentence_id", "sentence_text", "sentence_start", "sentence_end",
    "bunsetsu_id", "bunsetsu_text", "bunsetsu_start", "bunsetsu_end",
    "token_id", "text", "lemma", "pos", "tag", "morph", "start", "end",
    "head_id", "dependency", "entity_id", "entity_text", "entity_label",
    "entity_start", "entity_end", "coreference_mention",
    "coreference_mention_start", "coreference_mention_end",
    "antecedent", "antecedent_start", "antecedent_end", "coreference_method",
]

def _coreference_spans(doc, resolver):
    """Map mentions to character spans; never guess ambiguous occurrences."""
    links = []
    items = _heuristic_coreferences_doc(doc) if resolver is None else resolver(doc.text)
    for item in items:
        mention = item["mention"]
        if not isinstance(mention, str) or not mention:
            raise ValueError("Coreference mention must be a nonempty string")
        start = item.get("mention_start")
        end = item.get("mention_end")
        if start is None and end is None:
            start = doc.text.find(mention)
            if start < 0 or doc.text.find(mention,start+1) >= 0:
                raise ValueError("Ambiguous coreference mention: provide character offsets")
            end = start + len(mention)
        if not isinstance(start,int) or not isinstance(end,int) or not (
            0 <= start < end <= len(doc.text) and doc.text[start:end] == mention
        ):
            raise ValueError("Invalid coreference mention offsets")
        a,b = item["antecedent_start"],item["antecedent_end"]
        if not isinstance(a,int) or not isinstance(b,int) or not (
            0 <= a < b <= len(doc.text) and doc.text[a:b] == item["antecedent"]
        ):
            raise ValueError("Invalid coreference antecedent offsets")
        links.append((start,end,mention,item["antecedent"],a,b))
    return links

def analyze_text(data, *, text_column="text", id_column=None, model="ja_ginza",
                 enable_coreference=True, resolver=None):
    """Analyze each document once and return one row per token.

    IDs are zero-based within a document; character offsets are half-open.
    Sentence, bunsetsu and entity attributes repeat on their constituent tokens.
    Default coreference is a limited heuristic, not a general resolver.
    """
    import ginza
    rows = []
    for doc_id,doc in _parsed(data,text_column,id_column,model):
        sentence = {}
        for j,span in enumerate(doc.sents):
            for token in span:
                sentence[token.i] = (j,span.text,span.start_char,span.end_char)
        bunsetsu = {}
        for j,span in enumerate(ginza.bunsetu_spans(doc)):
            for token in span:
                bunsetsu[token.i] = (j,span.text,span.start_char,span.end_char)
        entity = {}
        for j,span in enumerate(doc.ents):
            for token in span:
                entity[token.i] = (j,span.text,span.label_,span.start_char,span.end_char)
        links = _coreference_spans(doc,resolver) if enable_coreference else []
        for token in doc:
            start,end = token.idx,token.idx+len(token.text)
            matches = [link for link in links if link[0] < end and start < link[1]]
            if len(matches)>1:
                raise ValueError("Multiple coreference links for one token are unsupported")
            coref = (None,)*7
            if matches:
                ms,me,mention,antecedent,a,b = matches[0]
                coref = (mention,ms,me,antecedent,a,b,
                         "heuristic" if resolver is None else "custom")
            rows.append((
                doc_id,*sentence.get(token.i,(None,)*4),
                *bunsetsu.get(token.i,(None,)*4),
                token.i,token.text,token.lemma_,token.pos_,token.tag_,
                str(token.morph),start,end,token.head.i,token.dep_,
                *entity.get(token.i,(None,)*5),*coref
            ))
    result = pd.DataFrame(rows,columns=ANALYSIS_COLUMNS)
    # Preserve the original local IDs and add globally usable identifiers.
    # A caller-supplied document ID is the stable identity across invocations.
    document_ids = {}
    for doc_id in result["doc_id"]:
        if doc_id not in document_ids:
            if id_column is None or isinstance(data,str):
                identity = uuid4()
            else:
                if isinstance(doc_id,Integral) and not isinstance(doc_id,bool):
                    key = int(doc_id)
                elif isinstance(doc_id,str) and doc_id.strip():
                    key = doc_id
                else:
                    raise ValueError("Document identifiers must be nonempty strings or integers")
                identity = uuid5(NAMESPACE_URL,"urn:zizai:nlp:"+json.dumps(key,ensure_ascii=False))
            document_ids[doc_id] = str(identity)
    result["doc_identifier"] = result["doc_id"].map(document_ids)
    for column,unit in (("sentence_id","sentence"),("bunsetsu_id","bunsetsu"),
                        ("token_id","token"),("entity_id","entity"),("head_id","token")):
        result[column.replace("_id","_identifier")] = [
            None if pd.isna(index) else str(uuid5(UUID(doc_identifier),f"{unit}:{int(index)}"))
            for doc_identifier,index in zip(result["doc_identifier"],result[column])
        ]
    return result

def analyze_keyword_importance(data, *, method, text_column="text", id_column=None,
                               model="ja_ginza", corpus=None,
                               embedding_model="cl-nagoya/ruri-v3-130m"):
    """Score all eligible keyword candidates without user-defined top-N filtering."""
    return extract_keywords(data,method=method,text_column=text_column,
                            id_column=id_column,model=model,top_n=None,
                            corpus=corpus,embedding_model=embedding_model)
