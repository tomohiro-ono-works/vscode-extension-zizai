# Taskの入口

2026-11-08：旧要件・設計の作り直しに伴い、旧Task一覧の運用を停止しています。利用者の完全削除の承認に基づき、不要な旧Issueを撤去し、以下の関連調査を保持します。状態は[Issue一覧](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues?q=is%3Aissue)で確認してください。

- [Notebook APIの調査記録 #14](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/14)
- [Python import・依存解決の調査記録 #20](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/20)
- [コネクタ出所・既存処理の調査記録 #25](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/25)

保持したIssueは過去の調査記録です。旧Taskのスコープ・完了条件・後続依頼を新方式の現行要件として適用しません。過去の不合格・未検証を変更していません。

## 新方式のTask

- [TASK-008 / #76：新方式の要件仕様書と参照入口の整備](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/76)
- [TASK-009 / #77：Notebook入力支援のVS Code拡張を作る](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/77)

仕様の正本は[新方式の要件仕様書](../features/requirements.md)。Taskの状態・結果はIssueで管理します。TASK-009はVS Code拡張のみを対象とし、3作業の各段階で必要な仕様確認・実装・検証を行います。残した[技術調査](../README.md)を再利用し、全詳細設計を先に完成させる進め方にはしません。

[Task・Subtask運用ルール](task-rules.md)・[Taskひな形](../../template/task.md)・[Subtaskひな形](../../template/subtask.md)
