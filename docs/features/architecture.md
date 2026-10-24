<a id="architecture"></a>
# アーキテクチャと責務分担

更新日：2026-10-23。

このプロジェクトの VS Code 拡張機能について、全体設計にある構成・責務・状態の所有者・境界を整理した資料です。[01 全体設計](../designs/01全体設計.md) を基準とし、Notebook の操作・保存の詳細は [02 Notebook UI 設計](../designs/02NotebookUI設計.md) に従います。

**設計上の責務を記載しています。アプリの実装・技術検証は未完了です。** 具体的なmetadataキー・パッケージ構成・正式な通信形式を、この資料で新しく確定しません。詳細フォームのサイドバー配置は[2026-10-22の決定](../decisions/2026-10-22-notebook-sidebar.md)を反映し、対象切替等は[2026-10-23に承認された設計](notebook-sidebar.md)に従います。正式契約・規約・開発入口を受けてから製品実装へ進みます。

<a id="runtime-topology"></a>
## 実行時の構成

```text
VS Code / Kiro IDE
└─ Jupyter Notebook (.ipynb)
   ├─ UI：HTML / CSS / JavaScript
   │  └─ セル側の選択、サイドバーフォーム、下書き・確定イベント
   ├─ Extension Host：Node.js + VS Code Notebook API
   │  └─ UI 通信、metadata・source 編集、Python コード生成
   └─ Jupyter 標準実行
      └─ Notebook で選択した既存 Python カーネル
         ├─ 初期化セル：import・インスタンス生成
         ├─ 処理セル：Python ライブラリ・コネクタの呼び出し
         └─ 標準の結果・Python 例外表示
```

拡張機能は処理を選択・設定するための UI とコード生成を提供します。Python の評価は、利用者が Jupyter 標準の ▶／Run All で行います。選択・フォーム編集・確定だけでは実行しません。

独自カーネル、独自実行サーバー、独自 Run All、Node.js と Python 間の DataFrame 同期は設けません。対象は通常の `.ipynb` であり、別アプリの Desktop Runtime や `.zizd` の実行方式を引き継ぎません。

<a id="current-responsibility-map"></a>
## コンポーネントの責務

| 構成要素 | 担当すること | 他の構成要素に任せること |
| --- | --- | --- |
| UI | 選択・フォーム・状態の表示、入力値の収集、下書き・確定イベントの通知 | Python コード生成、業務データ処理、Python 実行、OS 操作 |
| Extension Host | UI 通信、セル metadata 管理、Python コード生成、source 更新、初期化セル管理、ファイル／フォルダー選択などの OS 連携 | Python 実行、DataFrame 処理、Notebook 標準の結果・例外表示 |
| Notebook | セル source・metadata・標準出力を `.ipynb` として保存する | 独自の実行エンジン、Python オブジェクトの保持 |
| Jupyter カーネル | Python 実行、変数・DataFrame・インスタンスの保持、標準の結果・例外表示 | フォーム管理、VS Code のセル編集 |
| Python ライブラリ | カーネル内で呼び出す処理の基盤・共通ロジック | VS Code API、Notebook UI 管理 |
| コネクタ | ファイル形式・外部サービス等に対応するアクションの個別処理 | セルの生成・編集・表示管理 |

### ソースの配置先

| 配置先 | 配置する責務 |
| --- | --- |
| `apps/extension/` | Extension Host の処理 |
| `apps/gui/` | セル側の選択UIとサイドバーフォームの表示・入力部分 |
| `apps/core/` | Python ライブラリの処理基盤・共通ロジック |
| `apps/connectors/` | Python の個別コネクタ・アクション |
| `apps/common/` | 層をまたぐ契約・schema。形式・配布方式は未決定 |

配置先は実装を置くための区分です。正式なモジュール名・公開 API・Python パッケージ構成は未定です。`apps/common/` が Node.js と Python の双方から同じソースを直接 import する仕組みを意味するわけではありません。

<a id="dependency-boundaries"></a>
## 境界と処理の流れ

| 境界 | 渡すもの・担当 |
| --- | --- |
| UI → Extension Host | 処理識別子、フォーム値、選択・下書き編集・確定イベント。UI が Python source を組み立てない |
| Extension Host → UI | 選択候補、フォーム定義、保存済み設定、下書き、状態、エラーなどの表示情報 |
| Extension Host → Notebook | VS Code の編集 API による metadata・source 更新と初期化セルの生成 |
| Notebook → Jupyter | 通常の Python source を標準のセル実行で評価する |
| 生成 Python → Python ライブラリ・コネクタ | import、インスタンス生成、メソッド呼び出し、設定値。具体的なシグネチャは個別設計で定義する |
| Python 処理 → Notebook 出力 | カーネルの戻り値・オブジェクト・例外を標準表示する。DataFrame を Node.js 側に複製しない |

初期化セルは Notebook 先頭にコネクタごとに独立して生成し、同じコネクタでは再利用します。import を拡張機能の裏側で実行せず、初期化セルの source に記載して Jupyter が評価します。

コネクタ・アクションの Python 側の詳細 API、ライブラリ内部の import 関係、UI／Host 間のメッセージ形式は個別設計で決めます。別アプリの `execute(action, params, context)` や Bridge Protocol を、今回の確定済み契約として持ち込みません。

<a id="state-ownership"></a>
## 設定・実行状態の所有者

| 対象 | 所有・保持先 | 保存・復元の境界 |
| --- | --- | --- |
| セルモード、コネクタ、アクション | セル metadata。Extension Host が更新 | Notebook の通常保存・再オープンに従う |
| 確定済み設定と編集中の下書き | 区別してセル metadata に保持 | 下書きも保存対象。下書き編集だけでは source を変えない |
| 生成 Python コード | セル source。Extension Host が生成 | Notebook 保存の対象。手動編集はフォームに逆同期しない |
| 切り替え前の元 Python コード | Extension Host の一時メモリ | 同じ Notebook を開いている間のみ。閉じた後の復元は保証しない |
| 「未更新」などの一時状態 | 拡張機能の一時状態 | 実行成功検出・再オープン後の扱いは技術検証待ち |
| Python 変数・DataFrame・インスタンス | Notebook が選択した Jupyter カーネル | Node.js・metadata に複製せず、Jupyter 標準の変数共有に従う |
| 実行結果・Python 例外 | Notebook 標準出力 | `.ipynb` に保存され得る |

Notebook ごとのフォーム設定・拡張機能状態は独立させます。`config/` はローカル設定の配置先であり、セル設定の正本を metadata から移すものではありません。ローカル設定のファイル名・読み取り方式、ログの形式・保持期間は、この資料では定義しません。

## エラーと標準機能の境界

- フォーム検証、UI の描画・操作、コード生成、セル更新、OS 連携の失敗は拡張機能側で扱う。入力検証以外の具体的な通知方式は未定。
- Python 実行中の例外・結果・実行順序は Jupyter に委ねる。初回では Python 例外を Node.js に橋渡しする独自通知を設けない。
- セル削除・Undo・通常保存・折りたたみは Notebook 標準機能を使う。
- 独自結果 UI・100行単位のページネーションは優先度低い。初回は標準のセル出力を使う。

## 実装前に確認する事項

詳細フォームはサイドバーへ配置します。セル側の選択UIと標準のsource・出力を維持し、フォームの対象セル・下書き・非同期応答が混ざらないことを確認します。Notebook Rendererへ出力を挿入してフォームを常設する方式は採用しません。表示先が変わってもmetadata・sourceの所有者はExtension Hostです。

- VS Code / Kiro IDE の互換性、サイドバーの表示・対象切替・再表示時の復元、NodeFormの製品利用条件。
- metadata の正式キー、更新と dirty・Undo・性能、UI／Host 間のメッセージと非同期競合。
- 初期化セルと処理セルの識別、移動・複製・削除・Undo、元コード退避との対応。
- 実行成功の検出、「未更新」の状態遷移・再オープン時の復元。
- コネクタごとの API・依存関係、Python ライブラリの配布・参照方式と標準実行の結合。

## 正本と参考資料

- 全体方針の正本：[01 全体設計](../designs/01全体設計.md) の第2〜8節を中心に参照する。
- UI・保存・状態遷移の詳細：[02 Notebook UI 設計](../designs/02NotebookUI設計.md)。
- 本書：上記の設計上の責務と境界を、実装時に参照するために整理したもの。設計変更の際は関係する正本と併せて更新する。
- プロジェクトの概要：[README](../../README.md)。
- 別アプリのアーキテクチャ：[参考用の原資料](../research/other-app/architecture.md)。原資料の承認・実装状況・互換契約は本プロジェクトには適用しない。

未決定事項を補うために旧アプリの仕様を自動採用せず、責務や所有者が確定しない場合は、関係する Task に未確定であることを記録します。
