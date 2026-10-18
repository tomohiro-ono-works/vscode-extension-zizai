# アプリケーションの配置方針

本プロジェクトは VS Code 拡張機能と Python ライブラリで構成します。各フォルダーには、実装時に以下の責務を持つソースを配置します。

| 配置先 | 責務 | 境界 |
| --- | --- | --- |
| `extension/` | VS Code API、UI との通信、セル metadata の管理、Python コード生成、セル source の更新 | 業務データの処理や Python 実行は行わない |
| `gui/` | 処理選択、設定フォーム、入力・確定イベントなどの HTML / CSS / JavaScript | Python コード生成やコネクタ実行は行わない。Notebook 内での配置方式は技術検証で決める |
| `core/` | Jupyter カーネル内で利用する Python ライブラリの共通処理 | VS Code API を直接操作しない |
| `connectors/` | ファイル形式や外部サービスに対応する Python のアクション | 元アプリのコネクタ資料は参考資料。新拡張機能の実装済み仕様として扱わない |
| `common/` | 層をまたぐデータ定義、メッセージ契約、schema | Node.js と Python で同じソースを直接 import するという意味ではない。形式・配布方式は実装時に決める |

実行は Jupyter 標準のセル実行を使います。独立した `desktop/`・`cli/` や、Node.js と Python 間の DataFrame 同期基盤は設けません。

責務・状態の所有者・境界は [アーキテクチャ](../docs/features/architecture.md) に整理しています。モジュール名、公開 API、依存関係、パッケージ構成はまだ定義していません。概要は [プロジェクト README](../README.md)、全体方針の正本は [01 全体設計](../docs/designs/01全体設計.md)、UI の詳細は [02 Notebook UI 設計](../docs/designs/02NotebookUI設計.md) を参照し、個別 Task で具体化します。
