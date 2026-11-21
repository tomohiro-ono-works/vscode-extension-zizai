# テストと調査用の確認資産

現行アプリは[Pythonの単体・結合・配布確認](unit/python/README.md)と、下記のNotebookフォーム用サンプルを参照してください。

旧フォーム・サイドバーの試験資料と試作は、2026-11-08の設計作り直しで撤去しました。残した資産は過去の観測を追跡するもので、新方式の製品受入条件ではありません。

- [Notebook API診断](notebook-host-api/README.md)：セル編集・識別・保存・標準実行の観測。
- [パス選択試作](notebook-ui-gate/path-completion/extension.cjs)：補完選択後のダイアログ接続。
- [Python import調査](python-import-research/README.md)と[Python確認](unit/python/README.md)：独立したPython基盤の参照・配布確認。
- [選択カーネルでの過去の手順](manual/TASK-003-05-python.md)と[Notebook APIの過去の手順](manual/TASK-002-01-notebook-host.md)。

旧アプリの[候補選択とVS Code拡張の検証](https://github.com/tomohiro-ono-works/vscode-extension-zizai/blob/52795b5a28ebb032e87f12ebfbc32940acb962ac/apps/extension/README.md)および[旧フォーム契約の検証](https://github.com/tomohiro-ono-works/vscode-extension-zizai/blob/52795b5a28ebb032e87f12ebfbc32940acb962ac/tests/contracts/README.md)は、撤去前の固定版を参照してください。

## Pythonフォームの専用実機サンプル（TASK-010）

[準備・Playwrightセッション](e2e/python-form.cjs)は、専用venv・既存の隔離VS Code Insiders・公式Python/Jupyter拡張の読取コピーを使います。通常の利用者プロファイルや追跡中のsample Notebookを操作しません。ローカル環境のパス・版を固定した検証用で、汎用配布用の起動器ではありません。

起動例：`node tests/e2e/python-form.cjs results/新しい専用フォルダー`。既存の専用セッションの再開は同じパスと`--resume`を指定し、既存ログを保護します。GUI起動は合意した検証範囲と環境準備が前提です。Playwright操作要求は専用フォルダーの`request.json`、結果は`response.json`と`session.local.json`へ記録します。自動再生用テストスイートではなく、実行した操作と観測を保存するセッションです。

フォーム操作はPlaywright、OSのTkフォルダー選択・取消は利用者の手動操作として区別します。利用者へ渡したウィンドウに自動終了期限は設けません。終了承認後だけ、`authorization: "user_approved_end"`と`finish`操作で終了し、対象プロセス・ポートを確認します。結果は[既存証跡](../docs/research/notebook-ui/evidence/python-form-preview-20261112.json)へ集約し、未確認を合格にしません。

実行は[許可する操作方法](../docs/development.md#allowed-test-operations)に従います。
