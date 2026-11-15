# 既存コードの配置

TASK-011では外部CSV資産の正本をルートの`connectors/csv/`へ置き、共通の環境登録を`core/src/zizai/core/`、初回登録の公開入口を`connectors/src/zizai/connectors/`へ追加しています。2026-11-16に専用load方式から通常importへ変更しました。[現在の導入と状態](core/README.md)を参照してください。各分析プロジェクトへの同梱は不要です。以下はTASK-010時点の記録です。

TASK-010では`core/src/zizai`へPython Notebookフォームを追加しています。[フォームと配布経路](core/README.md)を参照してください。`connectors`の業務処理を実装済みとは扱いません。

2026-11-08の設計作り直しで旧責務表を撤去した時点では、`core/`と`connectors/`のPython最小基盤、および`common/`の旧契約schemaを変更していません。後のTASK-010による`core/`の変更は上記に区別しています。既存コードの存在を新方式の正式採用・実装完了とは扱いません。

Pythonコネクタ／アクションはVS Codeから独立させる方針です。TASK-010のフォーム・マジック・仮表示の境界は[現行要件](../docs/features/requirements.md)に定義しています。実業務コード生成は今回の実装範囲に含みません。[残した調査](../docs/README.md)は過去の記録として参照してください。
