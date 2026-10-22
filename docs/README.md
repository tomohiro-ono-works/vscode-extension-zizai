# ドキュメントの案内

## 開発時の入口

1. [プロジェクト README](../README.md) で、目的・構成・動作・現在の実装状況を確認する。
2. [開発手順](development.md) と [Task の案内](tasks/README.md) を読み、担当Issueと親Issueのゴール・スコープ・制約・完了条件を確認する。
3. 下記の参照順序で関係する設計を確認し、個別仕様・決定記録がある場合は併せて読む。

## 資料の配置と状態

| 配置先 | 用途 | 現在の状態 |
| --- | --- | --- |
| `features/` | 現行の責務・境界を整理したアーキテクチャと個別仕様 | [architecture.md](features/architecture.md) に今回の責務を整理。全体方針の正本は `designs/01全体設計.md` |
| [tasks/](tasks/README.md) | Issueへの入口と運用ルール | 作業範囲・進捗・判断・結果はGitHub Issuesで管理。既存のTask Markdownは移行元の記録 |
| `designs/` | 本プロジェクトの設計 | 下記の既存設計書を配置 |
| `research/` | 技術調査・参考資料 | 元アプリのコネクタ資料を配置 |
| `decisions/` | 本プロジェクトの判断と承認の記録 | 実際に判断・承認が行われた際に記録する |

### 設計書の参照順序

1. [01 全体設計](designs/01全体設計.md)：全体方針・責務・実行・配布・リリース範囲の正本。
2. [02 Notebook UI 設計](designs/02NotebookUI設計.md)：全体設計に沿った UI・保存・状態遷移の詳細。
3. [DESIGN.md](designs/DESIGN.md)：全体設計とほぼ重複する参考資料。Renderer の制約に関する補足を含む。

この順序は Notebook UI 設計に明記された優先順位に基づきます。プロジェクト README に全体設計と UI 詳細を統合し、`DESIGN.md` に追加されていた Renderer の注意点も取り込んでいます。元の設計書は詳細と統合元を確認するために保持しています。

設計上の決定事項と実装・動作確認の完了は別の状態です。現在はアプリの実装前であり、技術検証待ちの項目は各設計書とプロジェクト README に明記しています。

実装時に確認する責務・状態の所有者・境界は [アーキテクチャ](features/architecture.md) に整理しています。既存設計からの整理であり、新しい実行方式や API を確定するものではありません。

### 別アプリからの参考資料

[コネクタ別リファレンス](research/connectors/README.md) と関連 Markdown を `research/connectors/` にまとめています。これらは別アプリの調査資料であり、本プロジェクトの現行仕様や実装状況を表すものではありません。

原文には元アプリの Task、仕様、承認ログへの相対リンクや未収録の資料へのリンクがあります。その参照先は本リポジトリには含まれていません。元の承認を本プロジェクトの承認として扱わず、必要な資料は実装前に確認してください。

GitHub の `main` にあった [旧アプリのアーキテクチャ](research/other-app/architecture.md) も参考用に保管しています。PySide6、WorkflowEngine、`.zizd`、Bridge Protocol、旧アプリの承認・移行条件は今回の構成には適用しません。

GitHub に後から追加されていた README は [別アプリの文書管理参考資料](research/other-app/documentation-guide.md) として保持しています。今回の Task 作成は [Task・Subtask の作成ルール](tasks/task-rules.md) に従います。

<a id="document-responsibilities"></a>
## 文書と Task の役割

Task の領域・工程、Task／Subtask の分割、ID・Issueの関係、必須項目、完了判定は [Task・Subtask の作成ルール](tasks/task-rules.md) を基準にします。仕様・設計には製品の動作と責務、TaskのIssueには作業範囲・結果を記録し、資料索引やテスト定義と内容を重複させないようにします。

<a id="approval-boundaries"></a>
## 判断・承認の扱い

Task の作業権限は、依頼と Goal・Scope・Constraints・Acceptance Criteria の範囲で確認します。すでに許可された通常作業は進め、仕様・制約の変更など許可を超える判断が必要な場合は具体的な内容を確認します。取得していない承認や別アプリの承認を、本プロジェクトで取得済みと記録しません。記録方法は [Task 作成ルール](tasks/task-rules.md) に従います。
