# ドキュメントの案内

## 現在の状態

2026-11-08の利用者依頼により、旧要件・設計を撤去し、関係する調査だけを残しています。新方式の正本は[要件仕様書](features/requirements.md)です。確定した前提と、要求案・担当者提案・未決を区別しており、製品全体の仕様確定を意味しません。調査中の旧Task番号・承認・API案・未実施項目は当時の記録であり、新方式の要求や再試験条件ではありません。

## 残した調査

| 対象 | 資料・証跡 | 残す理由 |
| --- | --- | --- |
| Notebook編集API | [API調査](research/notebook-host/TASK-002-01.md)・同階層のevidence | セルsourceの編集、セル識別、保存、Undo／Redo、標準実行との共存に関する観測 |
| パス選択 | [試作結果](research/notebook-ui/evidence/path-completion-20261105.json)・[試作コード](../tests/notebook-ui-gate/path-completion/extension.cjs) | 補完後のダイアログと文字列置換の観測。新しいインライン選択UIの実証とは別 |
| Pythonの参照・配布 | [import調査](research/python-import/TASK-003-01.md)・同階層のevidence・[確認コード](../tests/python-import-research/README.md) | 選択カーネルと導入先の一致、importと依存解決、wheelの確認結果 |
| コネクタの既存処理 | [出所調査](research/connectors/TASK-004-01.md)・[個別資料](research/connectors/README.md) | Python業務処理の移管元。旧フォーム仕様を新方式に採用する意味ではない |
| 調査時の開発環境 | [環境記録](research/development/evidence/TASK-006-01-environment.json) | 当時の実行環境の記録。新しい対応版・配布方式の決定ではない |

廃止資料へのリンクは削除前の固定commitを参照します。[削除前の原文](https://github.com/tomohiro-ono-works/vscode-extension-zizai/tree/65631504f146a4dfa2ab52d557e58db53c2e6a00)は履歴で確認できます。過去の不合格・未検証を合格へ書き換えていません。

<a id="document-responsibilities"></a>
## 文書とTaskの役割

作業範囲・進捗・判断・結果はGitHub Issue、仕様詳細は設計資料へ記録します。[Task運用ルール](tasks/task-rules.md)と既存テンプレートは継続します。重複する管理文書は作りません。

<a id="approval-boundaries"></a>
## 判断・承認の扱い

承認済み判断、提案、未決事項を区別し、原文と出典を確認します。今回の設計撤去を理由に未決を承認済みと扱わず、旧調査の実施条件を新方式へ自動適用しません。

[開発・操作ルール](development.md)・[コーディングルール](../coding-rules.md)・[Taskの入口](tasks/README.md)
