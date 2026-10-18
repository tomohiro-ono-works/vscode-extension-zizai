> **注意：別アプリの参考資料です。**
> 本資料は別アプリの仕様・実装に基づいており、今回開発する VS Code 拡張機能の仕様・実装を示すものではありません。
> 記載されたコネクタの動作、入出力、実行方式、Task・承認情報は、本プロジェクトへの適用が未確定です。採用する内容は、本プロジェクト用に設計・検証してから反映します。

# DataintegrationConnector — 入力・出力リファレンス

- ラベル: #領域/コネクタ
- 確認日: 2026-10-17（作業ツリーの静的読取り）
- 位置づけ: 現行実装の調査資料。Current Specificationではない。
- [索引・共通の読み方](README.md)／[新結果形式と承認状態](README.md#new-result-format)

## 概要

前段の表データにRENAMEリストと列名クレンジング、行フィルターを適用する。pandasと共通schema処理を使用する。

## アクション一覧

| Action ID | 画面名 | 現在の戻り値 |
| --- | --- | --- |
| [replace_fields_forrenamelist](#replace_fields_forrenamelist) | フィールド名をRENAMEリストから変更 | DataFrame |
| [filter_rows](#filter_rows) | 条件指定 | DataFrame |

## 利用前提・共通境界

- 入り口: `execute(action, params, context)`。下記の入力例はparamsのみ。説明用の架空値であり、実行・外部接続による検証結果ではない。
- 出力例のdfは読みやすいrecords表現。実際の戻り値はDataFrameであり、JSON配列ではない。時刻・ID・path等は例示値。
- input_data／source_step_idを使う例は、必要な列を持つ前段結果がそのcontextキーにあることを前提とする。Engineへ保存するstep.output_variableも指定する。
- UI欄と実行側の条件・既定値は別。UIからの通常操作はUI値が渡るため、実行側省略値と一致するとは限らない。
- schemaの型・参照式は[共通データ契約](../../features/data-contract.md)を参照。schema適用後の値・列型は共通変換の影響を受ける。
- 未知actionは原則ValueError。依存・共通前提の検査が先に失敗する場合もある。

<a id="replace_fields_forrenamelist"></a>
## replace_fields_forrenamelist

用途: フィールド名をRENAMEリストから変更。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `input_data` | str | 必須 | 必須、既定 指定なし | contextのキー。例: step1。DataFrameそのものではなく参照名を指定。 |
| `rename_list_path` | str | 必須 | 必須、既定 "apps\\common\\config\\rename.csv" | 例: apps/common/config/rename.csv。相対pathはcontext.__repository_root基準。 |
| `pre_rename_cleansing` | list[str] / dict / JSON配列文字列 / カンマ区切り文字列 | 任意、未指定は適用なし | 任意／操作部品、既定 指定なし | 許容値は下記UI候補。dictは真の値のキーを採用。未知の指定は除外する。 UI候補: ["remove_spaces","remove_newlines","to_halfwidth_alnum","symbols_to_snake"]。 |
| `post_rename_cleansing` | list[str] / dict / JSON配列文字列 / カンマ区切り文字列 | 任意、未指定は適用なし | 任意／操作部品、既定 指定なし | 許容値は下記UI候補。dictは真の値のキーを採用。未知の指定は除外する。 UI候補: ["exclude_japanese_columns"]。 |
| `schema` | UI設定 | 実行側では読取なし | 任意／操作部品、既定 指定なし | このアクションのdispatch／処理はparamsの当該項目を参照しない。画面の存在を実行保証としない。 |

context: params.input_dataが指定するcontextキーから表を取得。DataFrame／list／dictを共通to_dataframeで扱う。

### 戻り値

型: `pandas.DataFrame`。列は取得した表の列であり固定しない。型はschema／推論に従い、解決済みschemaを`attrs["ziz_schema"]`へ保持する。

rename後の列名・型・説明をattrs.ziz_schemaへ保持。有効なrename定義がなければ警告logを出し入力表へschemaを付けて返す。

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "input_data": "step1",
  "rename_list_path": "apps/common/config/rename.csv"
}
```

出力の説明例:

```text
[ {"id":1,"new_name":"sample"} ]（対応するrename定義がある場合のdf例）
```

### エラー・副作用・制約

参照不足、相対pathのrepository_root不足、RENAMEファイル不在／必須列不足、共通schema適用エラー。入力表をcopyして加工し、RENAME CSVを読む。

RENAME CSVはorigin_nameとreplaced_name（またはnew_name）が必須。説明・型は任意。UIのschema入力は処理で参照せず、RENAME定義由来のschemaを使用。

根拠: [dataintegration_connector.py](../../../apps/connectors/dataintegration_connector.py)の`execute`（確認時L37）、`replace_fields_forrenamelist`（L44）。

<a id="filter_rows"></a>
## filter_rows

用途: 条件指定。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `input_data` | str | 必須 | 必須、既定 指定なし | contextのキー。例: step1。DataFrameそのものではなく参照名を指定。 |
| `conditions` | list[dict] / JSON配列文字列 | 任意、未指定は全行 | 任意／操作部品、既定 指定なし | 条件項目: field, operator, apply, value, value_to。全条件をANDで結合。 |
| `schema` | UI設定 | 実行側では読取なし | 任意／操作部品、既定 指定なし | このアクションのdispatch／処理はparamsの当該項目を参照しない。画面の存在を実行保証としない。 |

context: params.input_dataが指定するcontextキーから表を取得。DataFrame／list／dictを共通to_dataframeで扱う。

### 戻り値

型: `pandas.DataFrame`。列は取得した表の列であり固定しない。型はschema／推論に従い、解決済みschemaを`attrs["ziz_schema"]`へ保持する。

結果0行もdf。入力attrsのschemaをcopyして保持し、なければ推論。条件なしは入力を表へ変換して返す。

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "input_data": "step1",
  "conditions": [
    {
      "field": "name",
      "operator": "contains",
      "apply": "include",
      "value": "sample"
    }
  ]
}
```

出力の説明例:

```text
[ {"id":1,"name":"sample"} ]（一致した行のdf例）
```

### エラー・副作用・制約

参照不足、conditionsが配列でない、対象列不在、未知operator、rangeの端点不足、不正regex。入力dfのcopyを加工する。

operator: exact／prefix／suffix／contains（正規表現なし）／regex／range／is_null。applyはinclude／exclude、targetは別名。未知applyはincludeへ正規化。rangeは数値→日時→文字列で比較し両端を含む。is_nullは欠損と空白だけの文字列を対象。field／operatorのない条件や非dict要素は読み飛ばす。

根拠: [dataintegration_connector.py](../../../apps/connectors/dataintegration_connector.py)の`execute`（確認時L37）、`filter_rows`（L82）。

## 新結果形式との関係

両アクションはdataframeの割当案。列・型・値とschemaを保持する。

共通のresultType／result／meta、status・時刻・error等は[索引の新結果形式](README.md#new-result-format)と[最新のAction型割当](../../designs/TASK-048-action-result-design.md#result-type-allocation)を参照。新形式は製品未実装であり、本書の現在の戻り値へ既に付いているという意味ではない。

## 根拠・未確認事項

- 実装: [dataintegration_connector.py](../../../apps/connectors/dataintegration_connector.py)。共通表処理: [BaseConnector](../../../apps/core/base_connector.py)。
- UI宣言: [config.js](../../../apps/gui/config/config.js)のactions／forms。専用欄なしの引数は実装から補足。
- 共通仕様: [Connector契約](../../features/connectors.md)、[データ契約](../../features/data-contract.md)。
- 結果登録・template・loop・report: [WorkflowEngine](../../../apps/core/workflow_engine.py)。
- 調査Task: [TASK-053](../../tasks/done/TASK-053/TASK-053.md)。
- 未確認: 本Taskでは製品テスト・外部接続・OS入力・実ブラウザー・各保存先への書込を実行していない。環境依存の成否・性能は未検証。
- 更新時: 仕様と実装を再照合し、差異を記録する。実装観測だけを理由に現行仕様やTASK-048の決裁を書き換えない。
