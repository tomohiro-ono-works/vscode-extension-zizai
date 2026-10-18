# Task の管理

- [Task・Subtask の作成ルール](task-rules.md)：領域・工程、粒度、ID・配置、記載項目、完了判定の基準。
- `active/`：未完了の Task（未着手・進行中・保留。中止した Task は中止と明記）。
- `done/`：完了条件と結果を確認した Task。
- [Task のひな形](../../template/task.md)：新しい Task を記録する際に利用する。
- [Subtask のひな形](../../template/subtask.md)：親 Task 内への記載、または独立ファイルが必要な場合に利用する。

基本は領域ごとに Task を作り、具体的な作業を工程付きの Subtask に分けます。各 Task にゴール、スコープ、制約、完了条件、依存関係、必要な承認、検証結果、残作業を記録します。

文書の状態と実装の状態、クラウドの確認結果とデスクトップの確認結果を区別します。必要な工程を選び、全 Task に7工程の Subtask をそろえることは求めません。

## 未完了 Task の索引

現在、領域別の開発 Task は未作成です。作成時に ID・名前・領域・状態・親ファイルへのリンクをここへ追加します。

## 完了した作業記録

- [フォルダー・資料整理](done/2026-10-19-project-structure.md)
- [README の設計統合](done/2026-10-19-readme-integration.md)
- [アーキテクチャと責務分担](done/2026-10-19-project-architecture.md)

`docs/research/` の資料に登場する元アプリの Task 番号や承認は、このプロジェクトの Task・承認記録ではありません。
