# ZizAI

VS CodeのNotebook入力支援と、VS Codeに依存しないPythonコネクタ／アクションを検討するプロジェクトです。

## 現在の開発：Python Notebookフォーム

[TASK-010 / #82](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/82)で、`%form`から横並びの連動フォームをセル出力欄へ表示する方式へ改修中です。生成結果は現在`{csv.importのコードを生成}`等の仮表示です。[導入・YAML設定・現在の確認範囲](apps/core/README.md)と[未実行サンプル](examples/python-form.ipynb)を参照してください。独自VS Code拡張は必須とせず、従来の成果は以下の履歴として保持します。

## 設計の作り直し（2026-11-08）

利用者の依頼により、旧要件・設計・フォーム／サイドバーの試験資料を削除し、新方式に関係する調査を残しています。[新方式の要件仕様書](docs/features/requirements.md)に、確定した前提・利用者の要求案・担当者の構成案・未決事項をまとめました。製品全体の仕様確定・実装完了とは区別します。

Notebookのセル内候補選択・親子候補・ファイル／フォルダー選択と、YAMLによる入力支援定義をVS Code拡張の内部プレビューとして実装しています。[VSIXの作成・導入・使い方](apps/extension/README.md)を参照してください。専用Windows／Insidersでの自動・利用者操作確認を実施済みで、正式対応版・他環境は未決／未確認です。

スニペットの作成・登録は利用者が担当します。`@ziz`による雛形入力、階層的な`%%`マジックの実行・プログラム生成は拡張の今回の実装範囲外です。入力例のマジックを実行するPython接続部は含みません。

- [残した調査と文書の案内](docs/README.md)
- [開発・操作ルール](docs/development.md)
- [コーディングルール](coding-rules.md)
- [Taskの入口](docs/tasks/README.md)

既存のPython最小基盤・契約検証コードは今回変更していません。残存コードを新方式の正式仕様・完成した製品と扱わないでください。旧資料の原文と承認履歴はGit履歴で追跡できます。
