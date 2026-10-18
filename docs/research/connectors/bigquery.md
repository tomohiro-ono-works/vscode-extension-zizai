> **注意：別アプリの参考資料です。**
> 本資料は別アプリの仕様・実装に基づいており、今回開発する VS Code 拡張機能の仕様・実装を示すものではありません。
> 記載されたコネクタの動作、入出力、実行方式、Task・承認情報は、本プロジェクトへの適用が未確定です。採用する内容は、本プロジェクト用に設計・検証してから反映します。

# BQConnector — 入力・出力リファレンス

- ラベル: #領域/コネクタ
- 確認日: 2026-10-17（作業ツリーの静的読取り）
- 位置づけ: 現行実装の調査資料。Current Specificationではない。
- [索引・共通の読み方](README.md)／[新結果形式と承認状態](README.md#new-result-format)

## 概要

BigQueryのSQL実行とテーブルへのデータロード。google-cloud-bigquery、認証情報、対象projectへの権限が必要。実行には費用が発生し得る。

## アクション一覧

| Action ID | 画面名 | 現在の戻り値 |
| --- | --- | --- |
| [execute_sql](#execute_sql) | SQL実行 | DataFrame / None |
| [execute_sql_file](#execute_sql_file) | SQL実行（ファイル） | DataFrame / None |
| [load_data](#load_data) | データロード | DataFrame |

## 利用前提・共通境界

- 入り口: `execute(action, params, context)`。下記の入力例はparamsのみ。説明用の架空値であり、実行・外部接続による検証結果ではない。
- 出力例のdfは読みやすいrecords表現。実際の戻り値はDataFrameであり、JSON配列ではない。時刻・ID・path等は例示値。
- input_data／source_step_idを使う例は、必要な列を持つ前段結果がそのcontextキーにあることを前提とする。Engineへ保存するstep.output_variableも指定する。
- UI欄と実行側の条件・既定値は別。UIからの通常操作はUI値が渡るため、実行側省略値と一致するとは限らない。
- schemaの型・参照式は[共通データ契約](../../features/data-contract.md)を参照。schema適用後の値・列型は共通変換の影響を受ける。
- 未知actionは原則ValueError。依存・共通前提の検査が先に失敗する場合もある。

<a id="execute_sql"></a>
## execute_sql

用途: SQL実行。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `google_auth` | UI操作 | executeでは読取なし | 任意／操作部品、既定 指定なし | 認証ボタン用のUI項目。認証情報をparamsへ渡す引数ではない。 |
| `project_id` | str | 必須 | 必須、既定 "defult_project1" | BigQuery project ID。UI初期値は仮の候補で実projectを保証しない。 UI候補: ["defult_project1","defult_project2"]。 |
| `sql` | str | sql／sql_fileのどちらか一方 | 必須、既定 指定なし | 直接SQL。sql_queryはsql未指定時の別名。 |
| `schema` | list[dict] / JSON配列文字列 | 任意、未指定は推論 | 任意／操作部品、既定 指定なし | origin_name／new_name／description／ziz_datatypeの配列。共通データ契約を参照。 |
| `encoding` | str | 省略時 utf-8 | 専用欄なし | SQLファイルの文字コード。 |
| `is_output` | bool | 省略時 true | 専用欄なし | falseでもSQLは実行し、待機完了後の戻り値だけNoneにする。 |
| `sql_query` | str | 任意 | 専用欄なし | sqlの別名。sqlが優先。 |
| `sql_file` | str | sqlと排他 | 専用欄なし | SQLファイルのパス。 |

context: contextの業務データは参照しない。

### 戻り値

型: `pandas.DataFrame`。列は取得した表の列であり固定しない。型はschema／推論に従い、解決済みschemaを`attrs["ziz_schema"]`へ保持する。

非表SQLと判定され、job.schemaも取得行もない場合は次の1行表を返す。is_output=falseならNone。0行の表SQLはjob.schemaの列を使う空表。

| 列・項目 | 値の型 | 意味 |
| --- | --- | --- |
| `job_id` | str | Job ID |
| `project_id` | str | 実行project |
| `dataset_id` | str | 取得できた対象dataset |
| `table_id` | str | 取得できた対象table |
| `url` | str | BigQuery Console URL |
| `excuted_at` | TIMESTAMP | 完了時刻。現在の綴りはexcuted_at |

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "project_id": "example-project",
  "sql": "SELECT 1 AS id"
}
```

出力の説明例:

```text
[ {"id": 1} ]（DataFrameのrecords表現）
```

### エラー・副作用・制約

project_id不足、SQLの両方指定／両方なし、SQLファイル不在、schema不整合、認証・SQL・通信エラー。SQL内容に応じて外部テーブルを変更する。

SELECTだけをdfにする新方針は未実装。現行はstatement_type等の分岐で判定し、非表SQLのJob情報もDataFrameへ混在する。

根拠: [bigquery_connector.py](../../../apps/connectors/bigquery_connector.py)の`execute`（確認時L154）、`execute_sql`（L497）。

<a id="execute_sql_file"></a>
## execute_sql_file

用途: SQL実行（ファイル）。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `google_auth` | UI操作 | executeでは読取なし | 任意／操作部品、既定 指定なし | 認証ボタン用のUI項目。認証情報をparamsへ渡す引数ではない。 |
| `project_id` | str | 必須 | 必須、既定 "defult_project1" | BigQuery project ID。UI初期値は仮の候補で実projectを保証しない。 UI候補: ["defult_project1","defult_project2"]。 |
| `sql_file` | str | 必須 | 必須、既定 指定なし | 読込むSQLファイル。 |
| `encoding` | str | 省略時 utf-8 | 必須、既定 "utf8" | SQLファイルの文字コード。 UI候補: ["utf8","shift_jis"]。 |
| `schema` | list[dict] / JSON配列文字列 | 任意、未指定は推論 | 専用欄なし | origin_name／new_name／description／ziz_datatypeの配列。共通データ契約を参照。 |
| `is_output` | bool | 省略時 true | 専用欄なし | falseでもSQLは実行し、待機完了後の戻り値だけNoneにする。 |

context: contextの業務データは参照しない。

### 戻り値

型: `pandas.DataFrame`。列は取得した表の列であり固定しない。型はschema／推論に従い、解決済みschemaを`attrs["ziz_schema"]`へ保持する。

非表SQLと判定され、job.schemaも取得行もない場合は次の1行表を返す。is_output=falseならNone。0行の表SQLはjob.schemaの列を使う空表。

| 列・項目 | 値の型 | 意味 |
| --- | --- | --- |
| `job_id` | str | Job ID |
| `project_id` | str | 実行project |
| `dataset_id` | str | 取得できた対象dataset |
| `table_id` | str | 取得できた対象table |
| `url` | str | BigQuery Console URL |
| `excuted_at` | TIMESTAMP | 完了時刻。現在の綴りはexcuted_at |

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "project_id": "example-project",
  "sql_file": "sql/query.sql",
  "encoding": "utf-8"
}
```

出力の説明例:

```text
[ {"id": 1} ]（ファイル内容がSELECT 1 AS idの場合の表現例）
```

### エラー・副作用・制約

sql_file不足・不在、文字コード不正、認証・SQL・通信エラー。ファイル内容を外部DBで実行する。

根拠: [bigquery_connector.py](../../../apps/connectors/bigquery_connector.py)の`execute`（確認時L154）、`execute_sql_file`（L549）。

<a id="load_data"></a>
## load_data

用途: データロード。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `google_auth` | UI操作 | executeでは読取なし | 任意／操作部品、既定 指定なし | 認証ボタン用のUI項目。認証情報をparamsへ渡す引数ではない。 |
| `project_id` | str | 必須 | 必須、既定 "defult_project1" | BigQuery project ID。UI初期値は仮の候補で実projectを保証しない。 UI候補: ["defult_project1","defult_project2"]。 |
| `dataset_id` | str | 必須 | 必須、既定 "defult_dataset1" | 対象dataset ID。 UI候補: ["defult_dataset1","defult_dataset2"]。 |
| `table_id` | str | 必須 | 必須、既定 "defult_table" | 対象table ID。 |
| `input_data` | str | 必須 | 必須、既定 指定なし | contextのキー。例: step1。DataFrameそのものではなく参照名を指定。 |
| `write_disposition` | str | 省略時 create_or_replace | 必須、既定 "create_or_replace" | create_or_replace→WRITE_TRUNCATE、create_or_insert→WRITE_APPEND。他の値はSDKへ渡す。 UI候補: ["create_or_replace","create_or_insert"]。 |
| `schema_add_description` | UI設定 | 実行側では読取なし | 任意／操作部品、既定 指定なし | このアクションのdispatch／処理はparamsの当該項目を参照しない。画面の存在を実行保証としない。 |
| `schema` | list[dict] / JSON配列文字列 | 任意、未指定は推論 | 専用欄なし | origin_name／new_name／description／ziz_datatypeの配列。共通データ契約を参照。 |

context: context[input_data]からrecordsを取得。schemaは明示params.schema→DataFrame.attrs.ziz_schema→推論の順。

### 戻り値

型: `pandas.DataFrame`。取得データではなく、次のJob情報を持つ1行表。解決済みschemaはattrs.ziz_schemaへ保持。

| 列・項目 | 値の型 | 意味 |
| --- | --- | --- |
| `job_id` | str | Job ID |
| `project_id` | str | project |
| `dataset_id` | str | dataset |
| `table_id` | str | table |
| `url` | str | Console URL |
| `excuted_at` | TIMESTAMP | 完了時刻 |

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "project_id": "example-project",
  "dataset_id": "demo",
  "table_id": "items",
  "input_data": "step1",
  "write_disposition": "create_or_replace"
}
```

出力の説明例:

```text
[{"job_id":"example_job","project_id":"example-project","dataset_id":"demo","table_id":"items","url":"<Console URL>","excuted_at":"<完了時刻>"}]（1行df）
```

### エラー・副作用・制約

対象ID・入力参照不足、空入力、schema／型変換、認証・SDKエラー。既定では対象tableを置換する。

UIはschema_add_descriptionを宣言するが、Connectorはparams.schemaを読む。この差異の修正は本資料の範囲外。

根拠: [bigquery_connector.py](../../../apps/connectors/bigquery_connector.py)の`execute`（確認時L154）、`load_data`（L565）。

## 新結果形式との関係

SQL2件はSELECT時df／それ以外json、load_dataはjsonの割当案。SQL返却方針・配置の承認と、Action別の詳細schemaを区別。

共通のresultType／result／meta、status・時刻・error等は[索引の新結果形式](README.md#new-result-format)と[最新のAction型割当](../../designs/TASK-048-action-result-design.md#result-type-allocation)を参照。新形式は製品未実装であり、本書の現在の戻り値へ既に付いているという意味ではない。

## 根拠・未確認事項

- 実装: [bigquery_connector.py](../../../apps/connectors/bigquery_connector.py)。共通表処理: [BaseConnector](../../../apps/core/base_connector.py)。
- UI宣言: [config.js](../../../apps/gui/config/config.js)のactions／forms。専用欄なしの引数は実装から補足。
- 共通仕様: [Connector契約](../../features/connectors.md)、[データ契約](../../features/data-contract.md)。
- 結果登録・template・loop・report: [WorkflowEngine](../../../apps/core/workflow_engine.py)。
- 調査Task: [TASK-053](../../tasks/done/TASK-053/TASK-053.md)。
- 未確認: 本Taskでは製品テスト・外部接続・OS入力・実ブラウザー・各保存先への書込を実行していない。環境依存の成否・性能は未検証。
- 更新時: 仕様と実装を再照合し、差異を記録する。実装観測だけを理由に現行仕様やTASK-048の決裁を書き換えない。
