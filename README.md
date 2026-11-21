# ZizAI

ZizAIは、Jupyter Notebookのフォームで処理を選び、実行用のPythonコードを生成するアプリケーションです。VS Codeでは標準のPython／Jupyter拡張を使います。

- [インストールとフォームの使い方](docs/usage.md)
- [環境構築Notebook（手順書・設定スクリプト）](examples/setup-zizai.ipynb)
- [サンプルNotebook](examples/python-form.ipynb)・[CSVサンプル](examples/csv-form.ipynb)
- [現行要件](docs/features/requirements.md)・[Taskの入口](docs/tasks/README.md)
- [開発手順](docs/development.md)・[コーディングルール](coding-rules.md)
- [Kiro向けの作業ガイド](.kiro/steering/zizai.md)

`%load_ext zizai.forms` でフォームを登録し、`%form` で表示します。フォームで生成したPythonコードを、Notebookのコードセルに貼り付けて実行します。コネクタの配置と登録は導入手順を参照してください。

Pythonアプリのソースは `src/`、個別コネクタのPython実装とフォーム定義はルートの `connectors/` にあります。PythonスクリプトやKiroは、登録済みのコネクタを通常のimportで直接使えます。

旧VS Code入力支援拡張と旧フォーム契約の実装・使い方は、[旧入力支援拡張の手順](https://github.com/tomohiro-ono-works/vscode-extension-zizai/blob/52795b5a28ebb032e87f12ebfbc32940acb962ac/apps/extension/README.md)と[旧フォーム契約の手順](https://github.com/tomohiro-ono-works/vscode-extension-zizai/blob/52795b5a28ebb032e87f12ebfbc32940acb962ac/tests/contracts/README.md)に残しています。[保持した調査と検証結果](docs/README.md)も参照できます。
