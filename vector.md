# VectorConnector — 入力・出力リファレンス

- ラベル: #領域/コネクタ
- 確認日: 2026-10-17（作業ツリーの静的読取り）
- 位置づけ: 現行実装の調査資料。Current Specificationではない。
- [索引・共通の読み方](README.md)／[新結果形式と承認状態](README.md#new-result-format)

## 概要

埋め込みモデルとFAISS／DuckDBを使うベクトルDB構築・検索。numpy、faiss、duckdb、sentence-transformersが必要。初回モデル取得は通信・時間・保存容量を伴い得る。

## アクション一覧

| Action ID | 画面名 | 現在の戻り値 |
| --- | --- | --- |
| [embedding_vector_db](#embedding_vector_db) | ベクトルDB構築 | DataFrame |
| [search_vector_db](#search_vector_db) | ベクトル検索 | DataFrame |

## 利用前提・共通境界

- 入り口: `execute(action, params, context)`。下記の入力例はparamsのみ。説明用の架空値であり、実行・外部接続による検証結果ではない。
- 出力例のdfは読みやすいrecords表現。実際の戻り値はDataFrameであり、JSON配列ではない。時刻・ID・path等は例示値。
- input_data／source_step_idを使う例は、必要な列を持つ前段結果がそのcontextキーにあることを前提とする。Engineへ保存するstep.output_variableも指定する。
- UI欄と実行側の条件・既定値は別。UIからの通常操作はUI値が渡るため、実行側省略値と一致するとは限らない。
- schemaの型・参照式は[共通データ契約](../../features/data-contract.md)を参照。schema適用後の値・列型は共通変換の影響を受ける。
- 未知actionは原則ValueError。依存・共通前提の検査が先に失敗する場合もある。
- 構築例の前段表はid／text列を想定。モデル名は明示してUIと実行側の既定差を避ける。scoreの範囲・閾値はこの調査で保証していない。

<a id="embedding_vector_db"></a>
## embedding_vector_db

用途: ベクトルDB構築。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `db_folder` | str | 必須 | 必須、既定 指定なし | 保存先folder。展開・絶対化。構築はfolderを作り、検索は既存folder必須。 |
| `collection_name` | str | 必須 | 必須、既定 "default" | collection名。英数字・日本語・_・-。UI既定defaultを実行側は補わない。 |
| `input_data` | str | 必須 | 必須、既定 指定なし | contextのキー。例: step1。DataFrameそのものではなく参照名を指定。 |
| `id_column` | str | 必須 | 必須、既定 "id" | 一意ID列。行の値は非空、入力内重複不可。 |
| `text_column` | str | 必須 | 必須、既定 "text" | 埋め込み対象の非空text列。 |
| `model_name` | str | 省略・空値はcl-nagoya/ruri-v3-130m | 任意／操作部品、既定 "cl-nagoya/ruri-v3-30m" | UI既定cl-nagoya/ruri-v3-30mと異なる。既存collectionとモデル・次元を一致させる。 |

context: params.input_dataが指定するcontextキーから表を取得。DataFrame／list／dictを共通to_dataframeで扱う。

### 戻り値

型: `pandas.DataFrame`。

| 列・項目 | 値の型 | 意味 |
| --- | --- | --- |
| `collection_name` | str | collection名 |
| `registered_records` | int | 今回登録した入力record数 |
| `db_folder` | str | 絶対folder |
| `index_path` | str | collection.faiss |
| `metadata_path` | str | collection.duckdb |
| `model_name` | str | 使用モデル |
| `dimension` | int | ベクトル次元数 |

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "db_folder": "data/vector",
  "collection_name": "items",
  "input_data": "step1",
  "id_column": "id",
  "text_column": "text",
  "model_name": "cl-nagoya/ruri-v3-30m"
}
```

出力の説明例:

```text
[{"collection_name":"items","registered_records":2,"db_folder":"C:/example/data/vector","index_path":"C:/example/data/vector/items.faiss","metadata_path":"C:/example/data/vector/items.duckdb","model_name":"cl-nagoya/ruri-v3-30m","dimension":"<実モデルの次元数>"}]（1行df、dimensionの実型はint）
```

### エラー・副作用・制約

依存不足、入力不在・空表・指定列不足、空ID／text、重複ID、保存済みモデル／次元不一致。モデルをロードし、FAISSとDuckDBの2ファイルへ登録・同一IDを更新する。

ID／text以外の入力列はmetadata_jsonとしてDBへ保存する。

根拠: [vector_connector.py](../../../apps/connectors/vector_connector.py)の`execute`（確認時L40）、`embedding_vector_db`（L84）。

<a id="search_vector_db"></a>
## search_vector_db

用途: ベクトル検索。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `db_folder` | str | 必須 | 必須、既定 指定なし | 保存先folder。展開・絶対化。構築はfolderを作り、検索は既存folder必須。 |
| `collection_name` | str | 必須 | 必須、既定 "default" | collection名。英数字・日本語・_・-。UI既定defaultを実行側は補わない。 |
| `query_text` | str | 必須 | 必須、既定 指定なし | 検索文。 |
| `top_k` | int | 必須、1以上 | 必須、既定 5 | 取得上限。UI既定5を実行側では補わない。 |
| `include_vector` | bool / str | 省略時false | 必須、既定 "false" | true／1／yes／onでvector列を含める。 UI候補: ["false","true"]。 |
| `model_name` | str | 省略・空値はcl-nagoya/ruri-v3-130m | 任意／操作部品、既定 "cl-nagoya/ruri-v3-30m" | UI既定cl-nagoya/ruri-v3-30mと異なる。既存collectionとモデル・次元を一致させる。 |

context: contextの業務データは参照しない。

### 戻り値

型: `pandas.DataFrame`。

| 列・項目 | 値の型 | 意味 |
| --- | --- | --- |
| `id` | str | 登録ID |
| `text` | str | 登録text |
| `score` | float | FAISS検索score |
| `metadata` | str | 保存したmetadataのJSON文字列。dictではない |
| `collection_name` | str | collection名 |
| `vector` | str（任意列） | include_vector=true時のみ。ベクトルのJSON配列文字列 |

0件でもこの列集合の空df。上限はmin(top_k, index.ntotal)。

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "db_folder": "data/vector",
  "collection_name": "items",
  "query_text": "sample",
  "top_k": 5,
  "include_vector": false,
  "model_name": "cl-nagoya/ruri-v3-30m"
}
```

出力の説明例:

```text
[ {"id":"1","text":"sample","score":0.9,"metadata":"{}","collection_name":"items"} ]（dfのrecords表現例）
```

### エラー・副作用・制約

保存folder・2ファイル・設定不在、query不足、top_k不正、モデル・次元不一致、依存／モデル取得エラー。collectionを読取専用接続し、モデルをロードする。

根拠: [vector_connector.py](../../../apps/connectors/vector_connector.py)の`execute`（確認時L40）、`search_vector_db`（L153）。

## 新結果形式との関係

構築はjson、検索はdataframeの割当案。検索結果のmetadata列は登録した業務データであり共通metaとは別。

共通のresultType／result／meta、status・時刻・error等は[索引の新結果形式](README.md#new-result-format)と[最新のAction型割当](../../designs/TASK-048-action-result-design.md#result-type-allocation)を参照。新形式は製品未実装であり、本書の現在の戻り値へ既に付いているという意味ではない。

## 根拠・未確認事項

- 実装: [vector_connector.py](../../../apps/connectors/vector_connector.py)。共通表処理: [BaseConnector](../../../apps/core/base_connector.py)。
- UI宣言: [config.js](../../../apps/gui/config/config.js)のactions／forms。専用欄なしの引数は実装から補足。
- 共通仕様: [Connector契約](../../features/connectors.md)、[データ契約](../../features/data-contract.md)。
- 結果登録・template・loop・report: [WorkflowEngine](../../../apps/core/workflow_engine.py)。
- 調査Task: [TASK-053](../../tasks/done/TASK-053/TASK-053.md)。
- 未確認: 本Taskでは製品テスト・外部接続・OS入力・実ブラウザー・各保存先への書込を実行していない。環境依存の成否・性能は未検証。
- 更新時: 仕様と実装を再照合し、差異を記録する。実装観測だけを理由に現行仕様やTASK-048の決裁を書き換えない。
