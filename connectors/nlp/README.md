# NLP

`pip install -e ".[nlp]"` で依存関係を導入する。既存の configure_connectors で nlp を登録する。

```python
from nlp_connector import tokenize, extract_keywords, resolve_coreferences
result = tokenize('売上を分析してください。')
keywords = extract_keywords('売上を分析してください。', method='textrank')
```

全アクションは str または DataFrame を受け取り DataFrame を返す。文字位置は原文の0始まり、終了位置は排他的。TF-IDF は複数文書または corpus を必要とする。KeyBERT はモデル取得時に通信が発生し得る。共参照の既定実装は人物名と明示的代名詞に限定したルールベースであり、resolver 引数で差し替え可能。一般的な共参照やゼロ代名詞の解決は保証しない。
