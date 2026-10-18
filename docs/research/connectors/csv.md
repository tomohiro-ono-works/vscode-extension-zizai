> **注意：別アプリの参考資料です。**
> 本資料は別アプリの仕様・実装に基づいており、今回開発する VS Code 拡張機能の仕様・実装を示すものではありません。
> 記載されたコネクタの動作、入出力、実行方式、Task・承認情報は、本プロジェクトへの適用が未確定です。採用する内容は、本プロジェクト用に設計・検証してから反映します。

# CSVConnector — 入力・出力リファレンス

- ラベル: #領域/コネクタ
- 確認日: 2026-10-17（作業ツリーの静的読取り）
- 位置づけ: 現行実装の調査資料。Current Specificationではない。
- [索引・共通の読み方](README.md)／[新結果形式と承認状態](README.md#new-result-format)

## 概要

CSV／TSV等の表データの読込・出力。pandasを使用。文字コード、区切り文字、ヘッダー位置、型schemaを指定する。

## アクション一覧

| Action ID | 画面名 | 現在の戻り値 |
| --- | --- | --- |
| [read_csv](#read_csv) | 読み込み | DataFrame |
| [write_csv](#write_csv) | 書き込み | str |

## 利用前提・共通境界

- 入り口: `execute(action, params, context)`。下記の入力例はparamsのみ。説明用の架空値であり、実行・外部接続による検証結果ではない。
- 出力例のdfは読みやすいrecords表現。実際の戻り値はDataFrameであり、JSON配列ではない。時刻・ID・path等は例示値。
- input_data／source_step_idを使う例は、必要な列を持つ前段結果がそのcontextキーにあることを前提とする。Engineへ保存するstep.output_variableも指定する。
- UI欄と実行側の条件・既定値は別。UIからの通常操作はUI値が渡るため、実行側省略値と一致するとは限らない。
- schemaの型・参照式は[共通データ契約](../../features/data-contract.md)を参照。schema適用後の値・列型は共通変換の影響を受ける。
- 未知actionは現行executeに明示elseがなくNoneへ到達する。未知actionを明示エラーとする[現行契約](../../features/connectors.md#common-boundary)との差異。今回は挙動を記録し、修正しない。

<a id="read_csv"></a>
## read_csv

用途: 読み込み。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `file_path` | str | 必須 | 必須、既定 指定なし | 入力ファイル。例: data/input.csv。 |
| `encoding` | str | 省略時utf-8 | 必須、既定 "utf8" | 入力文字コード。UIはutf8。 UI候補: ["utf8","shift_jis","cp932"]。 |
| `delimiter` | str | 省略時 , | 必須、既定 "," | 区切り文字。\t／tab／TABはTABへ正規化。 UI候補: [",","\\t",";","&#124;"]。 |
| `header_row` | int | 省略時1、1以上 | 必須、既定 1 | ヘッダー行。1始まり。 |
| `data_start_row` | int | 省略時2、header_row以上 | 必須、既定 2 | データ開始行。1始まり。 |
| `chunk_size` | int | 省略時50000、0以上 | 任意／操作部品、既定 50000 | 1回の読取行数。0・空・Noneで分割なし。チャンクは最後に全件結合し、stream戻り値ではない。 |
| `date_cleansing` | bool相当 | 省略時true | 任意／操作部品、既定 true | 共通schema処理の日付クレンジング。 |
| `schema` | list[dict] / JSON配列文字列 | 任意、未指定は推論 | 任意／操作部品、既定 指定なし | origin_name／new_name／description／ziz_datatypeの配列。共通データ契約を参照。 |

context: 相対入力pathはcontext.__workspace_root→__flow_dir→cwdの順で存在を確認。いずれにもなければ正規化した元pathをreaderへ渡す。

### 戻り値

型: `pandas.DataFrame`。列は取得した表の列であり固定しない。型はschema／推論に従い、解決済みschemaを`attrs["ziz_schema"]`へ保持する。

EmptyDataErrorでは空dfへschemaを付けて返す。schema指定列が存在しない場合はエラー。

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "file_path": "data/items.csv",
  "encoding": "utf-8",
  "delimiter": ",",
  "header_row": 1,
  "data_start_row": 2
}
```

出力の説明例:

```text
[ {"id": 1, "name":"sample"} ]（入力に対応するdf例。実際の型はschema／推論次第）
```

### エラー・副作用・制約

file_path不足、行指定／chunk_size不正、ファイル不在・文字コード・schemaエラー。入力ファイルを読み、書換えはしない。

根拠: [csv_connector.py](../../../apps/connectors/csv_connector.py)の`execute`（確認時L61）、`read_csv`（L114）。

<a id="write_csv"></a>
## write_csv

用途: 書き込み。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `input_data` | str | 必須 | 必須、既定 指定なし | contextのキー。例: step1。DataFrameそのものではなく参照名を指定。 |
| `output_folder` | str | output_path未指定時はfile_nameとともに必須 | 必須、既定 指定なし | 出力先folder。自動作成はしない。 |
| `file_name` | str | output_path未指定時はoutput_folderとともに必須 | 必須、既定 "output.csv" | 出力ファイル名。拡張子なしの場合に補完。 |
| `encoding` | str | 省略時utf-8-sig | 必須、既定 "utf8" | UI既定utf8との違いあり。 UI候補: ["utf8","shift_jis","cp932"]。 |
| `delimiter` | str | 省略時 , | 必須、既定 "," | TAB指定の扱いはread_csvと同じ。 UI候補: [",","\\t",";","&#124;"]。 |
| `schema` | list[dict] / JSON配列文字列 | 任意、未指定は入力の列・値を使用 | 任意／操作部品、既定 指定なし | 指定時は共通schemaによる列選択・型・renameを適用。 |
| `output_path` | str | 任意、指定時はfolder／nameより優先 | 専用欄なし | 直接の出力path。UIに専用欄なし。 |

context: params.input_dataが指定するcontextキーから表を取得。DataFrame／list／dictを共通to_dataframeで扱う。

### 戻り値

型: `str`。内容は`CSV保存完了: {正規化した出力path}`。構造化したfile情報やstatus辞書ではない。

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "input_data": "step1",
  "output_folder": "outputs",
  "file_name": "items.csv",
  "encoding": "utf-8"
}
```

出力の説明例:

```text
"CSV保存完了: outputs/items.csv"
```

### エラー・副作用・制約

入力参照・出力先不足、入力不在・空表、schema・書込権限・親folder不在。index列なしでファイルを書き、既存fileは上書き。

根拠: [csv_connector.py](../../../apps/connectors/csv_connector.py)の`execute`（確認時L61）、`write_csv`（L219）。

## 新結果形式との関係

read_csvはdataframe、write_csvはjsonの割当案。現在の完了文字列が既に辞書になっている意味ではない。

共通のresultType／result／meta、status・時刻・error等は[索引の新結果形式](README.md#new-result-format)と[最新のAction型割当](../../designs/TASK-048-action-result-design.md#result-type-allocation)を参照。新形式は製品未実装であり、本書の現在の戻り値へ既に付いているという意味ではない。

## 根拠・未確認事項

- 実装: [csv_connector.py](../../../apps/connectors/csv_connector.py)。共通表処理: [BaseConnector](../../../apps/core/base_connector.py)。
- UI宣言: [config.js](../../../apps/gui/config/config.js)のactions／forms。専用欄なしの引数は実装から補足。
- 共通仕様: [Connector契約](../../features/connectors.md)、[データ契約](../../features/data-contract.md)。
- 結果登録・template・loop・report: [WorkflowEngine](../../../apps/core/workflow_engine.py)。
- 調査Task: [TASK-053](../../tasks/done/TASK-053/TASK-053.md)。
- 未確認: 本Taskでは製品テスト・外部接続・OS入力・実ブラウザー・各保存先への書込を実行していない。環境依存の成否・性能は未検証。
- 更新時: 仕様と実装を再照合し、差異を記録する。実装観測だけを理由に現行仕様やTASK-048の決裁を書き換えない。
