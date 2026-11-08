# 残した調査用の確認資産

新方式の[候補選択の文字列編集確認](unit/extension/selection.test.cjs)を追加しています。実行方法と現在の対象は[拡張ソースの案内](../apps/extension/README.md)を参照してください。これはCLIでのロジック確認であり、実画面の操作確認ではありません。

旧フォーム・サイドバーの試験資料と試作は、2026-11-08の設計作り直しで撤去しました。残した資産は過去の観測を追跡するもので、新方式の製品受入条件ではありません。

- [Notebook API診断](notebook-host-api/README.md)：セル編集・識別・保存・標準実行の観測。
- [パス選択試作](notebook-ui-gate/path-completion/extension.cjs)：補完選択後のダイアログ接続。
- [Python import調査](python-import-research/README.md)と[Python確認](unit/python/README.md)：独立したPython基盤の参照・配布確認。
- [選択カーネルでの過去の手順](manual/TASK-003-05-python.md)と[Notebook APIの過去の手順](manual/TASK-002-01-notebook-host.md)。

既存の[契約検証コード](contracts/README.md)はコード保護のため変更していません。旧フォーム契約の検証であり、新方式の必須条件にしません。

実行は[許可する操作方法](../docs/development.md#allowed-test-operations)に従います。今回の資料整理ではUI・kernel起動も過去の試験の再実行も行いません。
