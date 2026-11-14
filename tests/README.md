# 残した調査用の確認資産

新方式の[候補選択の文字列編集確認](unit/extension/selection.test.cjs)を追加しています。実行方法と現在の対象は[拡張ソースの案内](../apps/extension/README.md)を参照してください。これはCLIでのロジック確認であり、実画面の操作確認ではありません。

旧フォーム・サイドバーの試験資料と試作は、2026-11-08の設計作り直しで撤去しました。残した資産は過去の観測を追跡するもので、新方式の製品受入条件ではありません。

- [Notebook API診断](notebook-host-api/README.md)：セル編集・識別・保存・標準実行の観測。
- [パス選択試作](notebook-ui-gate/path-completion/extension.cjs)：補完選択後のダイアログ接続。
- [Python import調査](python-import-research/README.md)と[Python確認](unit/python/README.md)：独立したPython基盤の参照・配布確認。
- [選択カーネルでの過去の手順](manual/TASK-003-05-python.md)と[Notebook APIの過去の手順](manual/TASK-002-01-notebook-host.md)。

既存の[契約検証コード](contracts/README.md)はコード保護のため変更していません。旧フォーム契約の検証であり、新方式の必須条件にしません。

## Pythonフォームの専用実機サンプル（TASK-010）

[準備・Playwrightセッション](e2e/python-form.cjs)は、専用venv・既存の隔離VS Code Insiders・公式Python/Jupyter拡張の読取コピーを使います。通常の利用者プロファイルや追跡中のsample Notebookを操作しません。ローカル環境のパス・版を固定した検証用で、汎用配布用の起動器ではありません。

起動例：`node tests/e2e/python-form.cjs results/新しい専用フォルダー`。既存の専用セッションの再開は同じパスと`--resume`を指定し、既存ログを保護します。GUI起動は合意した検証範囲と環境準備が前提です。Playwright操作要求は専用フォルダーの`request.json`、結果は`response.json`と`session.local.json`へ記録します。自動再生用テストスイートではなく、実行した操作と観測を保存するセッションです。

フォーム操作はPlaywright、OSのTkフォルダー選択・取消は利用者の手動操作として区別します。利用者へ渡したウィンドウに自動終了期限は設けません。終了承認後だけ、`authorization: "user_approved_end"`と`finish`操作で終了し、対象プロセス・ポートを確認します。結果は[既存証跡](../docs/research/notebook-ui/evidence/python-form-preview-20261112.json)へ集約し、未確認を合格にしません。

実行は[許可する操作方法](../docs/development.md#allowed-test-operations)に従います。
