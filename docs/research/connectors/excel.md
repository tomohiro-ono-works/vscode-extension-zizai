> **注意：別アプリの参考資料です。**
> 本資料は別アプリの仕様・実装に基づいており、今回開発する VS Code 拡張機能の仕様・実装を示すものではありません。
> 記載されたコネクタの動作、入出力、実行方式、Task・承認情報は、本プロジェクトへの適用が未確定です。採用する内容は、本プロジェクト用に設計・検証してから反映します。

# ExcelConnector — 入力・出力リファレンス

- ラベル: #領域/コネクタ
- 確認日: 2026-10-17（作業ツリーの静的読取り）
- 位置づけ: 現行実装の調査資料。Current Specificationではない。
- [索引・共通の読み方](README.md)／[新結果形式と承認状態](README.md#new-result-format)

## 概要

Excelブックの通常読込・範囲読込・出力。pandas、openpyxlを使用。preview_excelは内部preview用で、画面の3アクションとは別。

## アクション一覧

| Action ID | 画面名 | 現在の戻り値 |
| --- | --- | --- |
| [read_excel](#read_excel) | 読み込み | DataFrame |
| [write_excel](#write_excel) | 書き込み | str |
| [read_excel_range](#read_excel_range) | エリア指定読み込み | DataFrame |

## 利用前提・共通境界

- 入り口: `execute(action, params, context)`。下記の入力例はparamsのみ。説明用の架空値であり、実行・外部接続による検証結果ではない。
- 出力例のdfは読みやすいrecords表現。実際の戻り値はDataFrameであり、JSON配列ではない。時刻・ID・path等は例示値。
- input_data／source_step_idを使う例は、必要な列を持つ前段結果がそのcontextキーにあることを前提とする。Engineへ保存するstep.output_variableも指定する。
- UI欄と実行側の条件・既定値は別。UIからの通常操作はUI値が渡るため、実行側省略値と一致するとは限らない。
- schemaの型・参照式は[共通データ契約](../../features/data-contract.md)を参照。schema適用後の値・列型は共通変換の影響を受ける。
- 未知actionは現行executeに明示elseがなくNoneへ到達する。未知actionを明示エラーとする[現行契約](../../features/connectors.md#common-boundary)との差異。今回は挙動を記録し、修正しない。

<a id="read_excel"></a>
## read_excel

用途: 読み込み。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `file_path` | str | 必須 | 必須、既定 指定なし | 入力ファイル。例: data/input.csv。 |
| `sheet_name` | str | 省略時空文字（active sheet） | 必須、既定 "シート1" | シート名。UI既定はシート1。 |
| `header_row` | int | 省略時1、1以上 | 必須、既定 1 | ヘッダー行。1始まり。 |
| `data_start_row` | int | 省略時2、header_row以上 | 必須、既定 2 | データ開始行。1始まり。 |
| `chunk_size` | int | 省略時50000、0以上 | 任意／操作部品、既定 50000 | 1回の読取行数。0・空・Noneで分割なし。チャンクは最後に全件結合し、stream戻り値ではない。 |
| `date_cleansing` | bool相当 | 省略時true | 任意／操作部品、既定 true | 共通schema処理の日付クレンジング。 |
| `schema` | list[dict] / JSON配列文字列 | 任意、未指定は推論 | 任意／操作部品、既定 指定なし | origin_name／new_name／description／ziz_datatypeの配列。共通データ契約を参照。 |

context: contextの業務データは参照しない。入力pathを正規化して開く。相対pathはcwd基準。

### 戻り値

型: `pandas.DataFrame`。列は取得した表の列であり固定しない。型はschema／推論に従い、解決済みschemaを`attrs["ziz_schema"]`へ保持する。

空行等の扱いは読込経路による。previewの物理30行契約は本取込とは別。

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "file_path": "data/items.xlsx",
  "sheet_name": "Sheet1",
  "header_row": 1,
  "data_start_row": 2
}
```

出力の説明例:

```text
[ {"id": 1, "name":"sample"} ]（dfのrecords表現例）
```

### エラー・副作用・制約

ファイル不在、sheet不在、行指定・chunk_size・schema不正。Excelを読込む。

根拠: [excel_connector.py](../../../apps/connectors/excel_connector.py)の`execute`（確認時L207）、`read_excel`（L434）。

<a id="write_excel"></a>
## write_excel

用途: 書き込み。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `input_data` | str | 必須 | 必須、既定 指定なし | contextのキー。例: step1。DataFrameそのものではなく参照名を指定。 |
| `output_folder` | str | output_path未指定時はfile_nameとともに必須 | 必須、既定 指定なし | 出力先folder。自動作成はしない。 |
| `file_name` | str | output_path未指定時はoutput_folderとともに必須 | 必須、既定 "output.xlsx" | 出力ファイル名。拡張子なしの場合に補完。 |
| `sheet_name` | str | 省略時Sheet1 | 必須、既定 "シート1" | 出力シート。UI既定はシート1。 |
| `mode` | str | 省略時create_or_replace | 必須、既定 "create_or_replace" | replaceは対象sheet置換、create_or_insertは末尾追記。insert_or_replaceはcreate_or_insertへ正規化。 UI候補: ["create_or_replace","create_or_insert"]。 |
| `schema` | list[dict] / JSON配列文字列 | 任意、未指定は入力の列・値を使用 | 任意／操作部品、既定 指定なし | 指定時は共通schemaによる列選択・型・renameを適用。 |
| `output_path` | str | 任意、指定時はfolder／nameより優先 | 専用欄なし | 直接の出力path。UIに専用欄なし。 |

context: params.input_dataが指定するcontextキーから表を取得。DataFrame／list／dictを共通to_dataframeで扱う。

### 戻り値

型: `str`。`Excel保存完了 [{mode}]: {path} (Sheet: {sheet_name})`。file情報辞書ではない。

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "input_data": "step1",
  "output_folder": "outputs",
  "file_name": "items.xlsx",
  "sheet_name": "Sheet1",
  "mode": "create_or_replace"
}
```

出力の説明例:

```text
"Excel保存完了 [create_or_replace]: outputs/items.xlsx (Sheet: Sheet1)"
```

### エラー・副作用・制約

参照・出力先不足、空入力、mode不正、schema／書込エラー。ファイルがなければ新規作成。replaceは対象sheet、insertは既存末尾へheaderなしで追加。親folderは作成しない。

根拠: [excel_connector.py](../../../apps/connectors/excel_connector.py)の`execute`（確認時L207）、`write_excel`（L513）。

<a id="read_excel_range"></a>
## read_excel_range

用途: エリア指定読み込み。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `file_path` | str | 必須 | 必須、既定 指定なし | 入力ファイル。例: data/input.csv。 |
| `sheet_name` | str | 省略時空文字（active sheet） | 必須、既定 "シート1" | シート名。UI既定はシート1。 |
| `cell_range` | str | 必須 | 必須、既定 指定なし | 例: A1:C20。header_row／data_start_rowは選んだ範囲内の1始まり位置。 |
| `header_row` | int | 省略時1、1以上 | 必須、既定 1 | ヘッダー行。1始まり。 |
| `data_start_row` | int | 省略時2、header_row以上 | 必須、既定 2 | データ開始行。1始まり。 |
| `date_cleansing` | bool相当 | 省略時true | 任意／操作部品、既定 true | 共通schema処理の日付クレンジング。 |
| `schema` | list[dict] / JSON配列文字列 | 任意、未指定は推論 | 任意／操作部品、既定 指定なし | origin_name／new_name／description／ziz_datatypeの配列。共通データ契約を参照。 |

context: contextの業務データは参照しない。

### 戻り値

型: `pandas.DataFrame`。列は取得した表の列であり固定しない。型はschema／推論に従い、解決済みschemaを`attrs["ziz_schema"]`へ保持する。

範囲内ヘッダーが空ならcol_0等で補完。全cellが空のデータ行は除外。単一cellでも同じ表構築へ進み、行指定によって0行になり得る。

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "file_path": "data/items.xlsx",
  "sheet_name": "Sheet1",
  "cell_range": "A1:B20",
  "header_row": 1,
  "data_start_row": 2
}
```

出力の説明例:

```text
[ {"id":1,"name":"sample"} ]（dfのrecords表現例）
```

### エラー・副作用・制約

ファイル／sheet不在、範囲不正、範囲外header／data_start、schema不整合。data_only=Trueで読取る。

通常読込とは実装経路が異なる。範囲読込へchunk_size設定は渡さない。

根拠: [excel_connector.py](../../../apps/connectors/excel_connector.py)の`execute`（確認時L207）、`read_excel_range`（L463）。

## 新結果形式との関係

読込2件はdataframe、出力はjsonの割当案。現行出力の完了文字列からfile情報を持つ成果へ変更する設計。

共通のresultType／result／meta、status・時刻・error等は[索引の新結果形式](README.md#new-result-format)と[最新のAction型割当](../../designs/TASK-048-action-result-design.md#result-type-allocation)を参照。新形式は製品未実装であり、本書の現在の戻り値へ既に付いているという意味ではない。

## 根拠・未確認事項

- 実装: [excel_connector.py](../../../apps/connectors/excel_connector.py)。共通表処理: [BaseConnector](../../../apps/core/base_connector.py)。
- UI宣言: [config.js](../../../apps/gui/config/config.js)のactions／forms。専用欄なしの引数は実装から補足。
- 共通仕様: [Connector契約](../../features/connectors.md)、[データ契約](../../features/data-contract.md)。
- 結果登録・template・loop・report: [WorkflowEngine](../../../apps/core/workflow_engine.py)。
- 調査Task: [TASK-053](../../tasks/done/TASK-053/TASK-053.md)。
- 未確認: 本Taskでは製品テスト・外部接続・OS入力・実ブラウザー・各保存先への書込を実行していない。環境依存の成否・性能は未検証。
- 更新時: 仕様と実装を再照合し、差異を記録する。実装観測だけを理由に現行仕様やTASK-048の決裁を書き換えない。
