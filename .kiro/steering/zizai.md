---
inclusion: always
---

# ZizAIでの作業

`pyproject.toml` がある `ZizAI` フォルダーをワークスペースとして開く。作業範囲・正本・検証ルールはルートの [AGENTS.md](../../AGENTS.md) と [開発手順](../../docs/development.md) を参照する。変更の進捗と判断は担当GitHub Issueで管理する。

## Notebookとコネクタの使い分け

- 人が設定を選ぶ場合は、NotebookのPythonセルで `%load_ext zizai.forms`、続けて `%form` を実行する。フォームは設定からPythonコードを生成する。コードは利用者がセルへ貼り付けて実行する。
- KiroやPythonスクリプトから処理する場合は、同じコネクタを通常のPython importで呼ぶ。カーネルまたは実行環境へのインストールと、共通フォルダーの登録方法は [導入手順](../../docs/usage.md) を参照する。登録は `from zizai.connectors import configure_connectors` が入口。
- 例えばCSVを読む場合は、登録後に以下のように呼び出す。分析経緯をNotebookへ残す依頼では、仮説や判断はMarkdownセル、実行した処理と結果はPythonセルとその出力に残す。

```python
import csv_connector

input_path = "C:/path/to/input.csv"
df = csv_connector.read_csv(file_path=input_path)
```

## 変更箇所と確認

- `src/` は共通フォーム、行プレビューUI、コネクタ登録と共通処理の正本。配布時は `zizai` パッケージになる。
- `connectors/<id>/` はコネクタ本体とフォーム定義YAMLの正本。専用のコード生成・フォーム補助は同じフォルダーの `form/` にあり、`zizai.connector_forms.<id>` として配布される。生成コードやPythonスクリプトからは `import csv_connector` などの通常importを使う。
- [テスト手順](../../tests/unit/python/README.md)を参照し、開発用環境にインストールした状態で確認する。フォームの検証はCLI/APIと合意した範囲のPlaywrightを使う。利用者が開いているNotebookや未保存変更を保護する。
