# アプリケーションの構成

| 場所 | 用途 |
| --- | --- |
| [`apps/core/`](core/README.md) | Python製Notebookフォーム、コード生成、共通処理と行プレビュー |
| [`apps/connectors/`](connectors/src/zizai/connectors/__init__.py) | 外部コネクタをPython環境へ登録する公開入口 |
| [ルートの `connectors/`](../connectors/) | 各コネクタのPython実装とフォーム定義 |
| [`pyproject.toml`](../pyproject.toml) | Pythonパッケージの配布定義 |

[導入手順](core/README.md)と[現行要件](../docs/features/requirements.md)を参照してください。
