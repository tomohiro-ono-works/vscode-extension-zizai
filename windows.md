# WindowsConnector — 入力・出力リファレンス

- ラベル: #領域/コネクタ, #領域/エンジン
- 確認日: 2026-10-17（作業ツリーの静的読取り）
- 位置づけ: 現行実装の調査資料。Current Specificationではない。
- [索引・共通の読み方](README.md)／[新結果形式と承認状態](README.md#new-result-format)

## 概要

変数定義、ファイル操作、検索、OS入力、待機、画面上のloop_tasksを扱う。pandas、pyautogui、pyperclipをimportする。入力操作にはWindows環境と操作対象画面が必要。loop_tasksの実行所有者はWorkflowEngine。

## アクション一覧

| Action ID | 画面名 | 現在の戻り値 |
| --- | --- | --- |
| [define_values](#define_values) | 変数定義 | DataFrame |
| [loop_tasks](#loop_tasks) | 繰り返し処理 | list[dict] |
| [rename_and_move_file](#rename_and_move_file) | ファイル名変更＆移動 | DataFrame |
| [search_files_by_name](#search_files_by_name) | ファイル名検索 | DataFrame |
| [search_text_in_files](#search_text_in_files) | ファイル内の文字列検索 | DataFrame |
| [create_markdown_file](#create_markdown_file) | マークダウンを作成 | DataFrame |
| [mouse_click](#mouse_click) | マウスクリック | DataFrame |
| [input_text](#input_text) | 文字列入力 | DataFrame |
| [send_keys](#send_keys) | キー入力 | DataFrame |
| [wait](#wait) | 待機 | DataFrame |

## 利用前提・共通境界

- 入り口: `execute(action, params, context)`。下記の入力例はparamsのみ。説明用の架空値であり、実行・外部接続による検証結果ではない。
- 出力例のdfは読みやすいrecords表現。実際の戻り値はDataFrameであり、JSON配列ではない。時刻・ID・path等は例示値。
- input_data／source_step_idを使う例は、必要な列を持つ前段結果がそのcontextキーにあることを前提とする。Engineへ保存するstep.output_variableも指定する。
- UI欄と実行側の条件・既定値は別。UIからの通常操作はUI値が渡るため、実行側省略値と一致するとは限らない。
- schemaの型・参照式は[共通データ契約](../../features/data-contract.md)を参照。schema適用後の値・列型は共通変換の影響を受ける。
- 未知actionは原則ValueError。依存・共通前提の検査が先に失敗する場合もある。

<a id="define_values"></a>
## define_values

用途: 変数定義。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `define_values` | list[dict] / dict / JSON文字列 | 任意、未指定は空配列 | 任意／操作部品、既定 指定なし | 配列要素はname・value。key／valも別名。dictはキーと値の組へ展開。 |

context: 名前の存在と固定変数をcontextで確認し、値を設定する。後続は通常変数{{limit}}として参照できる。

### 戻り値

型: `pandas.DataFrame`。

| 列・項目 | 値の型 | 意味 |
| --- | --- | --- |
| `variable_name` | str | 定義名 |
| `value` | 任意値 | 定義値 |
| `definition_type` | str | defined／overwritten |

有効な定義なしは0行・0列df。

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "define_values": [
    {
      "name": "limit",
      "value": 10
    }
  ]
}
```

出力の説明例:

```text
[ {"variable_name":"limit","value":10,"definition_type":"defined"} ]（1行df）
```

### エラー・副作用・制約

JSON／配列形式不正、配列に非dict、変数名不正。contextの変数を定義・上書きする。空のnameはskip。

変数名はひらがな・カタカナ・漢字・英数字・_。current_date／user_nameは既存context値を優先する固定変数。Engineも返却表から変数を反映する。

根拠: [windows_connector.py](../../../apps/connectors/windows_connector.py)の`execute`（確認時L28）、`define_values`（L88）。

<a id="loop_tasks"></a>
## loop_tasks

用途: 繰り返し処理。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `source_step_id` | str | input_dataとどちらか必要 | 必須、既定 指定なし | 反復対象のcontextキー。source_step_idを優先。 |
| `max_iterations` | int相当 | 省略・0・負値・不正値は上限制限なし | 任意／操作部品、既定 30 | 正の値なら先頭N件に限定。UI既定は30。 UI最小: 1。 |
| `input_data` | str | source_step_idの別名 | 専用欄なし | UI欄なし。 |

context: WorkflowEngine._execute_stepの専用経路。current_item／current_indexとsourceキーへ行を一時束縛。子stepのloop_owner_idとflowsの辺から子順序を構成。

### 戻り値

型: `list[dict]`。DataFrameはrecords、dictは1件の配列、list内のscalarは{"value": 値}へ変換。None／未存在キーは空配列。inline loop有効時はmax_iterationsで切った対象配列を返す。

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "source_step_id": "step1",
  "max_iterations": 30
}
```

出力の説明例:

```text
[ {"id":1}, {"id":2} ]（Pythonのlist[dict]）
```

### エラー・副作用・制約

参照名不足、反復対象の型不適合、子step失敗・cancel。子stepが持つ副作用を反復し、終了時に一時束縛を復元。

WindowsConnector.executeへ直接loop_tasksを渡すとUnknown action。Engine経由で実行する。通常flowではinline loop有効、単step実行では対象がloopかにより切替。無効時は子処理せずrecordsを返す。

根拠: [WorkflowEngine](../../../apps/core/workflow_engine.py)の`_execute_step`、`_normalize_loop_records`、`_index_loop_children`。

<a id="rename_and_move_file"></a>
## rename_and_move_file

用途: ファイル名変更＆移動。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `source_file_path` | str | 必須 | 必須、既定 指定なし | 移動元file。展開・絶対化。 |
| `destination_folder` | str | 変更先folder／file名のいずれか必要 | 任意／操作部品、既定 指定なし | 省略時は移動元folder。指定folderは作成。 |
| `destination_file_name` | str | 変更先folder／file名のいずれか必要 | 任意／操作部品、既定 指定なし | 省略時は移動元のbasename。 |
| `allow_missing_source` | bool相当 | 省略時false | 任意／操作部品、既定 false | 元file不在を警告log＋successの完了表としてskipする。 |

context: contextの業務データは参照しない。

### 戻り値

型: `pandas.DataFrame`。

| 列・項目 | 値の型 | 意味 |
| --- | --- | --- |
| `status` | str | success |
| `executed_at` | str | UTCのISO日時 |
| `connector` | str | Connector名 |
| `action` | str | Action ID |
| `target` | str | 処理対象 |
| `message` | str | 完了message |

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "source_file_path": "data/items.csv",
  "destination_folder": "outputs",
  "destination_file_name": "items-done.csv"
}
```

出力の説明例:

```text
[ {"status":"success","executed_at":"2026-10-17T01:00:00+00:00","connector":"WindowsConnector","action":"rename_and_move_file","target":"<対象>","message":"<完了message>"} ]（1行df）
```

### エラー・副作用・制約

元file不在・file以外、変更先両方なし、移動失敗。shutil.moveで実fileを移動。既存の移動先の扱いはOS／shutilへ依存し、独自上書き保護を断定しない。

targetは移動後path。allow_missing_source=trueでskipした場合は元指定path。成功表のstatusだけで移動済みと判断せずmessageも確認する。

根拠: [windows_connector.py](../../../apps/connectors/windows_connector.py)の`execute`（確認時L28）、`rename_and_move_file`（L118）。

<a id="search_files_by_name"></a>
## search_files_by_name

用途: ファイル名検索。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `root_folder` | str | 必須 | 必須、既定 指定なし | 存在する検索root folder。~展開・絶対化。 |
| `recursive` | bool相当 | 省略時false | 任意／操作部品、既定 false | 子folderも検索するか。 |
| `file_name_pattern` | str | 任意、空値は無条件 | 任意／操作部品、既定 指定なし | basenameに対する正規表現。 |
| `file_extension_pattern` | str | 任意、空値は無条件 | 任意／操作部品、既定 指定なし | 先頭.を除く拡張子に対する正規表現。例: csv&#124;xlsx。 |
| `max_elapsed_seconds` | int | 省略・空値は120、30〜480 | 必須、既定 120 | 最大経過秒。file単位の判定であり処理中fileを即時中断しない。 UI最小: 30。 UI最大: 480。 |

context: contextの業務データは参照しない。

### 戻り値

型: `pandas.DataFrame`。

| 列・項目 | 値の型 | 意味 |
| --- | --- | --- |
| `folder_path` | str | folderの絶対path |
| `file_name` | str | 拡張子付きbasename |

0件もこの2列の空df。timeout状態は列へ含めずlogだけ。

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "root_folder": "data",
  "recursive": false,
  "file_extension_pattern": "csv",
  "max_elapsed_seconds": 120
}
```

出力の説明例:

```text
[ {"folder_path":"C:/example/data","file_name":"items.csv"} ]（df）
```

### エラー・副作用・制約

root不在・folder以外、regex／時間値不正、探索失敗。file情報を読む。制限時間到達は警告logと部分結果で返す。

根拠: [windows_connector.py](../../../apps/connectors/windows_connector.py)の`execute`（確認時L28）、`search_files_by_name`（L178）。

<a id="search_text_in_files"></a>
## search_text_in_files

用途: ファイル内の文字列検索。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `root_folder` | str | 必須 | 必須、既定 指定なし | 存在する検索root folder。~展開・絶対化。 |
| `recursive` | bool相当 | 省略時false | 任意／操作部品、既定 false | 子folderも検索するか。 |
| `file_name_pattern` | str | 任意、空値は無条件 | 任意／操作部品、既定 指定なし | basenameに対する正規表現。 |
| `file_extension_pattern` | str | 任意、空値は無条件 | 任意／操作部品、既定 指定なし | 先頭.を除く拡張子に対する正規表現。例: csv&#124;xlsx。 |
| `content_pattern` | str | 必須 | 必須、既定 指定なし | 行ごとの検索正規表現。 |
| `context_lines` | int | 省略時0、0以上 | 必須、既定 0 | 前後に含める行数。UI上限200は実行側では検証しない。 UI最小: 0。 UI最大: 200。 |
| `max_elapsed_seconds` | int | 省略・空値は120、30〜480 | 必須、既定 120 | 最大経過秒。file単位の判定であり処理中fileを即時中断しない。 UI最小: 30。 UI最大: 480。 |

context: contextの業務データは参照しない。

### 戻り値

型: `pandas.DataFrame`。

| 列・項目 | 値の型 | 意味 |
| --- | --- | --- |
| `folder_path` | str | folderの絶対path |
| `file_name` | str | basename |
| `line_number` | int | 1始まりの一致行番号 |
| `matched_line` | str | 一致した1行 |
| `context_excerpt` | str | 前後行を改行で連結 |

0件もこの5列。utf-8→utf-8-sig→cp932→shift_jisで読取を試す。

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "root_folder": "data",
  "content_pattern": "error",
  "context_lines": 1,
  "max_elapsed_seconds": 120
}
```

出力の説明例:

```text
[ {"folder_path":"C:/example/data","file_name":"log.txt","line_number":2,"matched_line":"error","context_excerpt":"before\nerror\nafter"} ]（df）
```

### エラー・副作用・制約

root／regex／非負行数／時間値不正、探索失敗。内容の読取に失敗したfileはskip。時間到達は警告logと部分結果で返す。

根拠: [windows_connector.py](../../../apps/connectors/windows_connector.py)の`execute`（確認時L28）、`search_text_in_files`（L208）。

<a id="create_markdown_file"></a>
## create_markdown_file

用途: マークダウンを作成。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `write_mode` | str | 省略・空値はreplace | 必須、既定 "replace" | replace／append。 UI候補: ["replace","append"]。 |
| `target_file_path` | str | 必須 | 必須、既定 指定なし | 拡張子なしなら.md。~展開・絶対化。親folderを作成。 |
| `content` | str | 省略・None・空値は空文字 | 必須、既定 指定なし | 保存する本文。UIでは必須。 |

context: contextの業務データは参照しない。

### 戻り値

型: `pandas.DataFrame`。

| 列・項目 | 値の型 | 意味 |
| --- | --- | --- |
| `status` | str | success |
| `executed_at` | str | UTCのISO日時 |
| `connector` | str | Connector名 |
| `action` | str | Action ID |
| `target` | str | 処理対象 |
| `message` | str | 完了message |

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "write_mode": "replace",
  "target_file_path": "outputs/report.md",
  "content": "# Report\nSample"
}
```

出力の説明例:

```text
[ {"status":"success","executed_at":"2026-10-17T01:00:00+00:00","connector":"WindowsConnector","action":"create_markdown_file","target":"<対象>","message":"<完了message>"} ]（1行df）
```

### エラー・副作用・制約

mode不正、path不足、書込権限・I/Oエラー。UTF-8で新規作成・置換・追記。targetは解決後のpath。

根拠: [windows_connector.py](../../../apps/connectors/windows_connector.py)の`execute`（確認時L28）、`create_markdown_file`（L154）。

<a id="mouse_click"></a>
## mouse_click

用途: マウスクリック。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `coordinate_mode` | str | 省略時specified | 必須、既定 "specified" | specified／current。 UI候補: ["current","specified"]。 |
| `x` | int | specified時に必要 | 必須（表示条件: {"key":"coordinate_mode","in":["specified",""]}）、既定 指定なし | 画面X座標。 |
| `y` | int | specified時に必要 | 必須（表示条件: {"key":"coordinate_mode","in":["specified",""]}）、既定 指定なし | 画面Y座標。 |
| `coordinate_picker` | UI操作 | 実行側では読取なし | 任意／操作部品（表示条件: {"key":"coordinate_mode","in":["specified",""]}）、既定 指定なし | x／y入力の補助ボタン。 |
| `button` | str | 省略時left | 必須、既定 "left" | left／right。 UI候補: ["left","right"]。 |
| `click_count` | int | 省略時1 | 必須、既定 "1" | 1または2。 UI候補: ["1","2"]。 |

context: contextの業務データは参照しない。

### 戻り値

型: `pandas.DataFrame`。

| 列・項目 | 値の型 | 意味 |
| --- | --- | --- |
| `status` | str | success |
| `executed_at` | str | UTCのISO日時 |
| `connector` | str | Connector名 |
| `action` | str | Action ID |
| `target` | str | 処理対象 |
| `message` | str | 完了message |

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "coordinate_mode": "specified",
  "x": 640,
  "y": 480,
  "button": "left",
  "click_count": 1
}
```

出力の説明例:

```text
[ {"status":"success","executed_at":"2026-10-17T01:00:00+00:00","connector":"WindowsConnector","action":"mouse_click","target":"<対象>","message":"<完了message>"} ]（1行df）
```

### エラー・副作用・制約

Windows以外、座標不正、button／回数不正、OS入力失敗。pyautoguiで画面座標をclick。targetはscreen:(x, y)。

根拠: [windows_connector.py](../../../apps/connectors/windows_connector.py)の`execute`（確認時L28）、`mouse_click`（L243）。

<a id="input_text"></a>
## input_text

用途: 文字列入力。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `input_mode` | str | 省略時replace | 必須、既定 "replace" | replace／append。replaceはCtrl+A後に貼付け。 UI候補: ["replace","append"]。 |
| `text` | str | キー存在と非Noneが必要、空文字は可 | 必須、既定 指定なし | 入力する本文。 |

context: contextの業務データは参照しない。

### 戻り値

型: `pandas.DataFrame`。

| 列・項目 | 値の型 | 意味 |
| --- | --- | --- |
| `status` | str | success |
| `executed_at` | str | UTCのISO日時 |
| `connector` | str | Connector名 |
| `action` | str | Action ID |
| `target` | str | 処理対象 |
| `message` | str | 完了message |

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "input_mode": "append",
  "text": "sample"
}
```

出力の説明例:

```text
[ {"status":"success","executed_at":"2026-10-17T01:00:00+00:00","connector":"WindowsConnector","action":"input_text","target":"<対象>","message":"<完了message>"} ]（1行df）
```

### エラー・副作用・制約

text不在／None、mode不正、Windows以外、OS入力失敗。ASCIIで改行・TABのないtextはpyautogui.write。それ以外はclipboardへcopyしCtrl+V後、finallyで以前のclipboard textを復元する。

根拠: [windows_connector.py](../../../apps/connectors/windows_connector.py)の`execute`（確認時L28）、`input_text`（L268）。

<a id="send_keys"></a>
## send_keys

用途: キー入力。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `modifier_keys` | list / tuple / set / str | 任意 | 任意／操作部品、既定 指定なし | ctrl／shift／alt。文字列はカンマまたは+で分割、小文字化・重複除去。 UI候補: ["ctrl","shift","alt"]。 |
| `key` | str | 必須 | 必須、既定 指定なし | 英数字1字、F1〜F24、特殊キー。前後空白除去・小文字化。ENTER／ESCは可、RETURN／ESCAPEは別名として受理しない。 |
| `wait_seconds` | int | 省略時0、0以上 | 任意／操作部品、既定 0 | キー送信後の待機秒。 UI最小: 0。 |

context: contextの業務データは参照しない。

### 戻り値

型: `pandas.DataFrame`。

| 列・項目 | 値の型 | 意味 |
| --- | --- | --- |
| `status` | str | success |
| `executed_at` | str | UTCのISO日時 |
| `connector` | str | Connector名 |
| `action` | str | Action ID |
| `target` | str | 処理対象 |
| `message` | str | 完了message |

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "modifier_keys": [
    "ctrl"
  ],
  "key": "s",
  "wait_seconds": 0
}
```

出力の説明例:

```text
[ {"status":"success","executed_at":"2026-10-17T01:00:00+00:00","connector":"WindowsConnector","action":"send_keys","target":"<対象>","message":"<完了message>"} ]（1行df）
```

### エラー・副作用・制約

key／modifier不正、待機値不正、Windows以外、OS入力失敗。active windowへhotkey送信。

根拠: [windows_connector.py](../../../apps/connectors/windows_connector.py)の`execute`（確認時L28）、`send_keys`（L288）。

<a id="wait"></a>
## wait

用途: 待機。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `duration_seconds` | int | 省略時1、0〜600 | 必須、既定 1 | 待機秒。 UI最小: 0。 UI最大: 600。 |

context: contextの業務データは参照しない。

### 戻り値

型: `pandas.DataFrame`。

| 列・項目 | 値の型 | 意味 |
| --- | --- | --- |
| `status` | str | success |
| `executed_at` | str | UTCのISO日時 |
| `connector` | str | Connector名 |
| `action` | str | Action ID |
| `target` | str | 処理対象 |
| `message` | str | 完了message |

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "duration_seconds": 1
}
```

出力の説明例:

```text
[ {"status":"success","executed_at":"2026-10-17T01:00:00+00:00","connector":"WindowsConnector","action":"wait","target":"<対象>","message":"<完了message>"} ]（1行df）
```

### エラー・副作用・制約

待機値が非整数・負値・600超。指定秒sleepする。targetはactive_windowだがOS入力はしない。

根拠: [windows_connector.py](../../../apps/connectors/windows_connector.py)の`execute`（確認時L28）、`wait`（L304）。

## 新結果形式との関係

検索・変数定義はdataframe、ファイル操作・OS操作・待機・loopはjsonの割当案。loopのlistもjsonに含む。

共通のresultType／result／meta、status・時刻・error等は[索引の新結果形式](README.md#new-result-format)と[最新のAction型割当](../../designs/TASK-048-action-result-design.md#result-type-allocation)を参照。新形式は製品未実装であり、本書の現在の戻り値へ既に付いているという意味ではない。

## 根拠・未確認事項

- 実装: [windows_connector.py](../../../apps/connectors/windows_connector.py)。共通表処理: [BaseConnector](../../../apps/core/base_connector.py)。
- UI宣言: [config.js](../../../apps/gui/config/config.js)のactions／forms。専用欄なしの引数は実装から補足。
- 共通仕様: [Connector契約](../../features/connectors.md)、[データ契約](../../features/data-contract.md)。
- 結果登録・template・loop・report: [WorkflowEngine](../../../apps/core/workflow_engine.py)。
- 調査Task: [TASK-053](../../tasks/done/TASK-053/TASK-053.md)。
- 未確認: 本Taskでは製品テスト・外部接続・OS入力・実ブラウザー・各保存先への書込を実行していない。環境依存の成否・性能は未検証。
- 更新時: 仕様と実装を再照合し、差異を記録する。実装観測だけを理由に現行仕様やTASK-048の決裁を書き換えない。
