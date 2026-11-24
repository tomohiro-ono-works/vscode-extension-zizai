"""Japanese NLP operations with DataFrame outputs."""
from functools import lru_cache
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
            scores = [{names[j]:float(x) for j,x in zip(row.indices,row.data)} for row in matrix]
        else: scores = [{} for _ in lists]
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
            embedding_model, device="cpu", trust_remote_code=False,
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
    """Conservative baseline: explicit third-person pronouns and preceding person entities.
    This is not a general Japanese coreference model; ambiguous candidates are skipped.
    """
    doc = _model("ja_ginza")(text)
    for token in doc:
        if token.pos_ != "PRON" or token.text not in {"彼","彼女","彼ら"}:
            continue
        candidates = [e for e in doc.ents if e.end <= token.i and e.label_ in {"Person","PERSON"}]
        unique = {e.text:e for e in candidates}
        if len(unique) != 1 or token.text == "彼ら":
            continue
        e = next(iter(unique.values()))
        yield {"mention":token.text,"antecedent":e.text,
               "antecedent_start":e.start_char,"antecedent_end":e.end_char}
