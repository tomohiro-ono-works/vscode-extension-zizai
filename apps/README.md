# 既存コードの配置

TASK-010では`core/src/zizai`へPython Notebookフォームを追加しています。[フォームと配布経路](core/README.md)を参照してください。`connectors`の業務処理を実装済みとは扱いません。

設計作り直しに伴い旧責務表を撤去しました。`core/`と`connectors/`のPython最小基盤、および`common/`の旧契約schemaは今回変更していません。既存コードの存在を新方式の正式採用・実装完了とは扱いません。

Pythonコネクタ／アクションはVS Codeから独立させる方針です。拡張とPython magicの具体的な境界・生成方式は今後の要件定義で決定します。[残した調査](../docs/README.md)を参照してください。
