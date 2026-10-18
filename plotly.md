# PlotlyConnector — 入力・出力リファレンス

- ラベル: #領域/コネクタ
- 確認日: 2026-10-17（作業ツリーの静的読取り）
- 位置づけ: 現行実装の調査資料。Current Specificationではない。
- [索引・共通の読み方](README.md)／[新結果形式と承認状態](README.md#new-result-format)

## 概要

前段の表から5種類のグラフを作成し、ファイルへ保存する。pandas、plotlyを使用。画像・PDF・SVG出力には利用環境の画像export依存も必要。

## アクション一覧

| Action ID | 画面名 | 現在の戻り値 |
| --- | --- | --- |
| [plot_combined_bar_line](#plot_combined_bar_line) | 棒＋折れ線グラフ | str |
| [plot_stacked_bar](#plot_stacked_bar) | 積み上げ棒グラフ | str |
| [plot_scorecard](#plot_scorecard) | スコアカード | str |
| [plot_funnel](#plot_funnel) | ファネルチャート | str |
| [plot_radar](#plot_radar) | レーダーチャート | str |

## 利用前提・共通境界

- 入り口: `execute(action, params, context)`。下記の入力例はparamsのみ。説明用の架空値であり、実行・外部接続による検証結果ではない。
- 出力例のdfは読みやすいrecords表現。実際の戻り値はDataFrameであり、JSON配列ではない。時刻・ID・path等は例示値。
- input_data／source_step_idを使う例は、必要な列を持つ前段結果がそのcontextキーにあることを前提とする。Engineへ保存するstep.output_variableも指定する。
- UI欄と実行側の条件・既定値は別。UIからの通常操作はUI値が渡るため、実行側省略値と一致するとは限らない。
- schemaの型・参照式は[共通データ契約](../../features/data-contract.md)を参照。schema適用後の値・列型は共通変換の影響を受ける。
- 未知actionは原則ValueError。依存・共通前提の検査が先に失敗する場合もある。
- 例の前段表はmonth／sales／profit列を想定。scorecardはsalesの最終2行を使う。画像依存を前提にしない使用例としてhtmlを指定。戻り値のpath区切りはOS依存で、説明例は/表記。

<a id="plot_combined_bar_line"></a>
## plot_combined_bar_line

用途: 棒＋折れ線グラフ。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `input_data` | str | input_data／json_dataのどちらか必要 | 必須、既定 指定なし | contextキー。指定時はjson_dataより優先。 |
| `x_col` | str | 必要な列 | 必須、既定 指定なし | X軸の列。 |
| `bar_col` | str | 必要な列 | 必須、既定 指定なし | 棒グラフの値列。 |
| `line_col` | str | 必要な列 | 必須、既定 指定なし | 折れ線の値列。 |
| `title` | str | 省略時 棒グラフ＋折れ線グラフ | 任意／操作部品、既定 "棒グラフ＋折れ線グラフ" | グラフのタイトル。 |
| `output_folder` | str | output_folder／folderが必要 | 必須、既定 指定なし | 保存folder。不在なら作成。 |
| `file_name` | str | 省略時 combined_bar_line | 必須、既定 "combined_bar_line" | 拡張子なしのファイル名。 |
| `mode` | str | 省略時png | 必須、既定 "png" | png／html／jpg／jpeg／pdf／svg。 UI候補: ["png","html","jpg","jpeg","pdf","svg"]。 |
| `json_data` | DataFrame / list / dict | input_data未指定時に必要 | 専用欄なし | 直接の表データ。JSON文字列をparseする引数ではない。 |
| `folder` | str | output_folderの別名 | 専用欄なし | UI欄なし。 |

context: input_data指定時はcontextから取得。未指定時はjson_dataを直接to_dataframeへ渡す。

### 戻り値

型: `str`。`os.path.join(folder, file_name + "." + mode)`で生成した保存path。絶対化しない。Figure、画像bytes、集計表ではない。

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "input_data": "step1",
  "x_col": "month",
  "bar_col": "sales",
  "line_col": "profit",
  "output_folder": "outputs",
  "file_name": "combined_bar_line",
  "mode": "html"
}
```

出力の説明例:

```text
"outputs/combined_bar_line.html"
```

### エラー・副作用・制約

入力参照不在、必要列不足、形式不正、空表条件、画像export依存・保存エラー。保存folderとfileを作成し、同名fileは保存処理で上書き。

軸の出現順を保持してgroupbyし、値列を数値化して合計。変換不能値は0。

根拠: [plotly_connector.py](../../../apps/connectors/plotly_connector.py)の`execute`（確認時L254）、`plot_combined_bar_line`（L293）。

<a id="plot_stacked_bar"></a>
## plot_stacked_bar

用途: 積み上げ棒グラフ。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `input_data` | str | input_data／json_dataのどちらか必要 | 必須、既定 指定なし | contextキー。指定時はjson_dataより優先。 |
| `x_col` | str | 必要な列 | 必須、既定 指定なし | X軸の列。 |
| `y_cols` | list / tuple / str | 必須 | 必須、既定 指定なし | 値列の配列またはカンマ区切り。 |
| `is_percent` | bool | 省略時false | 任意／操作部品、既定 "" | bool()評価。trueで100%積上げ。文字列falseは真になるためbool値を使う。 UI候補: ["","1"]。 |
| `title` | str | 省略時 積み上げ棒グラフ | 任意／操作部品、既定 "積み上げ棒グラフ" | グラフのタイトル。 |
| `output_folder` | str | output_folder／folderが必要 | 必須、既定 指定なし | 保存folder。不在なら作成。 |
| `file_name` | str | 省略時 stacked_bar | 必須、既定 "stacked_bar" | 拡張子なしのファイル名。 |
| `mode` | str | 省略時png | 必須、既定 "png" | png／html／jpg／jpeg／pdf／svg。 UI候補: ["png","html","jpg","jpeg","pdf","svg"]。 |
| `json_data` | DataFrame / list / dict | input_data未指定時に必要 | 専用欄なし | 直接の表データ。JSON文字列をparseする引数ではない。 |
| `folder` | str | output_folderの別名 | 専用欄なし | UI欄なし。 |

context: input_data指定時はcontextから取得。未指定時はjson_dataを直接to_dataframeへ渡す。

### 戻り値

型: `str`。`os.path.join(folder, file_name + "." + mode)`で生成した保存path。絶対化しない。Figure、画像bytes、集計表ではない。

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "input_data": "step1",
  "x_col": "month",
  "y_cols": [
    "sales",
    "profit"
  ],
  "output_folder": "outputs",
  "file_name": "stacked_bar",
  "mode": "html"
}
```

出力の説明例:

```text
"outputs/stacked_bar.html"
```

### エラー・副作用・制約

入力参照不在、必要列不足、形式不正、空表条件、画像export依存・保存エラー。保存folderとfileを作成し、同名fileは保存処理で上書き。

軸ごとに値列を合計する。

根拠: [plotly_connector.py](../../../apps/connectors/plotly_connector.py)の`execute`（確認時L254）、`plot_stacked_bar`（L307）。

<a id="plot_scorecard"></a>
## plot_scorecard

用途: スコアカード。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `input_data` | str | input_data／json_dataのどちらか必要 | 必須、既定 指定なし | contextキー。指定時はjson_dataより優先。 |
| `value_col` | str | 必要な列 | 必須、既定 指定なし | 指標列。 |
| `title` | str | 省略時 スコアカード | 任意／操作部品、既定 "スコアカード" | グラフのタイトル。 |
| `output_folder` | str | output_folder／folderが必要 | 必須、既定 指定なし | 保存folder。不在なら作成。 |
| `file_name` | str | 省略時 scorecard | 必須、既定 "scorecard" | 拡張子なしのファイル名。 |
| `mode` | str | 省略時png | 必須、既定 "png" | png／html／jpg／jpeg／pdf／svg。 UI候補: ["png","html","jpg","jpeg","pdf","svg"]。 |
| `json_data` | DataFrame / list / dict | input_data未指定時に必要 | 専用欄なし | 直接の表データ。JSON文字列をparseする引数ではない。 |
| `folder` | str | output_folderの別名 | 専用欄なし | UI欄なし。 |

context: input_data指定時はcontextから取得。未指定時はjson_dataを直接to_dataframeへ渡す。

### 戻り値

型: `str`。`os.path.join(folder, file_name + "." + mode)`で生成した保存path。絶対化しない。Figure、画像bytes、集計表ではない。

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "input_data": "step1",
  "value_col": "sales",
  "output_folder": "outputs",
  "file_name": "scorecard",
  "mode": "html"
}
```

出力の説明例:

```text
"outputs/scorecard.html"
```

### エラー・副作用・制約

入力参照不在、必要列不足、形式不正、空表条件、画像export依存・保存エラー。保存folderとfileを作成し、同名fileは保存処理で上書き。

最後の行の値を表示し、1つ前の行と比較。1行だけなら同じ値を基準にする。空表はエラー。

根拠: [plotly_connector.py](../../../apps/connectors/plotly_connector.py)の`execute`（確認時L254）、`plot_scorecard`（L322）。

<a id="plot_funnel"></a>
## plot_funnel

用途: ファネルチャート。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `input_data` | str | input_data／json_dataのどちらか必要 | 必須、既定 指定なし | contextキー。指定時はjson_dataより優先。 |
| `stage_col` | str | 必要な列 | 必須、既定 指定なし | 段階列。 |
| `value_col` | str | 必要な列 | 必須、既定 指定なし | 値列。 |
| `title` | str | 省略時 ファネルチャート | 任意／操作部品、既定 "ファネルチャート" | グラフのタイトル。 |
| `output_folder` | str | output_folder／folderが必要 | 必須、既定 指定なし | 保存folder。不在なら作成。 |
| `file_name` | str | 省略時 funnel | 必須、既定 "funnel" | 拡張子なしのファイル名。 |
| `mode` | str | 省略時png | 必須、既定 "png" | png／html／jpg／jpeg／pdf／svg。 UI候補: ["png","html","jpg","jpeg","pdf","svg"]。 |
| `json_data` | DataFrame / list / dict | input_data未指定時に必要 | 専用欄なし | 直接の表データ。JSON文字列をparseする引数ではない。 |
| `folder` | str | output_folderの別名 | 専用欄なし | UI欄なし。 |

context: input_data指定時はcontextから取得。未指定時はjson_dataを直接to_dataframeへ渡す。

### 戻り値

型: `str`。`os.path.join(folder, file_name + "." + mode)`で生成した保存path。絶対化しない。Figure、画像bytes、集計表ではない。

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "input_data": "step1",
  "stage_col": "month",
  "value_col": "sales",
  "output_folder": "outputs",
  "file_name": "funnel",
  "mode": "html"
}
```

出力の説明例:

```text
"outputs/funnel.html"
```

### エラー・副作用・制約

入力参照不在、必要列不足、形式不正、空表条件、画像export依存・保存エラー。保存folderとfileを作成し、同名fileは保存処理で上書き。

段階ごとに値を合計する。

根拠: [plotly_connector.py](../../../apps/connectors/plotly_connector.py)の`execute`（確認時L254）、`plot_funnel`（L334）。

<a id="plot_radar"></a>
## plot_radar

用途: レーダーチャート。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `input_data` | str | input_data／json_dataのどちらか必要 | 必須、既定 指定なし | contextキー。指定時はjson_dataより優先。 |
| `value_cols` | list / tuple / str | 通常UIでは必須 | 必須、既定 指定なし | 列別合計を軸にする値列。配列またはカンマ区切り。 |
| `name` | str | 省略時series | 任意／操作部品、既定 "series" | 系列名。 |
| `title` | str | 省略時 レーダーチャート | 任意／操作部品、既定 "レーダーチャート" | グラフのタイトル。 |
| `output_folder` | str | output_folder／folderが必要 | 必須、既定 指定なし | 保存folder。不在なら作成。 |
| `file_name` | str | 省略時 radar | 必須、既定 "radar" | 拡張子なしのファイル名。 |
| `mode` | str | 省略時png | 必須、既定 "png" | png／html／jpg／jpeg／pdf／svg。 UI候補: ["png","html","jpg","jpeg","pdf","svg"]。 |
| `json_data` | DataFrame / list / dict | input_data未指定時に必要 | 専用欄なし | 直接の表データ。JSON文字列をparseする引数ではない。 |
| `folder` | str | output_folderの別名 | 専用欄なし | UI欄なし。 |
| `theta_col` | str | value_colsなしの場合必要 | 専用欄なし | 縦持ちデータの軸列。UI欄なし。 |
| `r_col` | str | value_colsなしの場合必要 | 専用欄なし | 縦持ちデータの値列。UI欄なし。 |

context: input_data指定時はcontextから取得。未指定時はjson_dataを直接to_dataframeへ渡す。

### 戻り値

型: `str`。`os.path.join(folder, file_name + "." + mode)`で生成した保存path。絶対化しない。Figure、画像bytes、集計表ではない。

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "input_data": "step1",
  "value_cols": [
    "sales",
    "profit"
  ],
  "output_folder": "outputs",
  "file_name": "radar",
  "mode": "html"
}
```

出力の説明例:

```text
"outputs/radar.html"
```

### エラー・副作用・制約

入力参照不在、必要列不足、形式不正、空表条件、画像export依存・保存エラー。保存folderとfileを作成し、同名fileは保存処理で上書き。

value_colsありは各列合計、なしはtheta_colごとのr_col合計。空表はエラー。

根拠: [plotly_connector.py](../../../apps/connectors/plotly_connector.py)の`execute`（確認時L254）、`plot_radar`（L347）。

## 新結果形式との関係

5件ともjsonの割当案。生成したfile名・pathは成果としてresultに保持し、実行状態はmetaへ分ける。

共通のresultType／result／meta、status・時刻・error等は[索引の新結果形式](README.md#new-result-format)と[最新のAction型割当](../../designs/TASK-048-action-result-design.md#result-type-allocation)を参照。新形式は製品未実装であり、本書の現在の戻り値へ既に付いているという意味ではない。

## 根拠・未確認事項

- 実装: [plotly_connector.py](../../../apps/connectors/plotly_connector.py)。共通表処理: [BaseConnector](../../../apps/core/base_connector.py)。
- UI宣言: [config.js](../../../apps/gui/config/config.js)のactions／forms。専用欄なしの引数は実装から補足。
- 共通仕様: [Connector契約](../../features/connectors.md)、[データ契約](../../features/data-contract.md)。
- 結果登録・template・loop・report: [WorkflowEngine](../../../apps/core/workflow_engine.py)。
- 調査Task: [TASK-053](../../tasks/done/TASK-053/TASK-053.md)。
- 未確認: 本Taskでは製品テスト・外部接続・OS入力・実ブラウザー・各保存先への書込を実行していない。環境依存の成否・性能は未検証。
- 更新時: 仕様と実装を再照合し、差異を記録する。実装観測だけを理由に現行仕様やTASK-048の決裁を書き換えない。
