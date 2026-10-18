# ShellConnector — 入力・出力リファレンス

- ラベル: #領域/コネクタ
- 確認日: 2026-10-17（作業ツリーの静的読取り）
- 位置づけ: 現行実装の調査資料。Current Specificationではない。
- [索引・共通の読み方](README.md)／[新結果形式と承認状態](README.md#new-result-format)

## 概要

Windows BATをshell=Trueで実行する。stdout／stderrはcp932で読取り、変換不能文字は置換する。BATは任意の外部変更を行い得る。

## アクション一覧

| Action ID | 画面名 | 現在の戻り値 |
| --- | --- | --- |
| [execute_bat](#execute_bat) | バッチ実行 | DataFrame |

## 利用前提・共通境界

- 入り口: `execute(action, params, context)`。下記の入力例はparamsのみ。説明用の架空値であり、実行・外部接続による検証結果ではない。
- 出力例のdfは読みやすいrecords表現。実際の戻り値はDataFrameであり、JSON配列ではない。時刻・ID・path等は例示値。
- input_data／source_step_idを使う例は、必要な列を持つ前段結果がそのcontextキーにあることを前提とする。Engineへ保存するstep.output_variableも指定する。
- UI欄と実行側の条件・既定値は別。UIからの通常操作はUI値が渡るため、実行側省略値と一致するとは限らない。
- schemaの型・参照式は[共通データ契約](../../features/data-contract.md)を参照。schema適用後の値・列型は共通変換の影響を受ける。
- 未知actionは原則ValueError。依存・共通前提の検査が先に失敗する場合もある。

<a id="execute_bat"></a>
## execute_bat

用途: バッチ実行。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `file_path` | str | 必須 | 必須、既定 指定なし | 存在するBATファイル。 |
| `args` | str / list / tuple / scalar | 省略時空文字 | 任意／操作部品、既定 指定なし | strはshell引数文字列をそのまま連結。list／tupleはlist2cmdlineで組立。 |

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
| `stdout` | str | stripした標準出力 |
| `stderr` | str | stripした標準エラー |
| `returncode` | int | 正常完了コード（check=True） |

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "file_path": "scripts/example.bat",
  "args": [
    "sample",
    "two words"
  ]
}
```

出力の説明例:

```text
[ {"status":"success","executed_at":"2026-10-17T01:00:00+00:00","connector":"ShellConnector","action":"execute_bat","target":"scripts/example.bat","message":"BAT実行成功","stdout":"done","stderr":"","returncode":0} ]（1行df）
```

### エラー・副作用・制約

file_path不足・不在、プロセス異常終了。非zeroはRuntimeErrorでstdout／stderrを含む。BAT実行の副作用は取り消さない。

根拠: [shell_connector.py](../../../apps/connectors/shell_connector.py)の`execute`（確認時L12）、`execute_bat`（L21）。

## 新結果形式との関係

jsonの割当案。stdout／stderr等の成果と実行情報の具体schemaは評価対象。

共通のresultType／result／meta、status・時刻・error等は[索引の新結果形式](README.md#new-result-format)と[最新のAction型割当](../../designs/TASK-048-action-result-design.md#result-type-allocation)を参照。新形式は製品未実装であり、本書の現在の戻り値へ既に付いているという意味ではない。

## 根拠・未確認事項

- 実装: [shell_connector.py](../../../apps/connectors/shell_connector.py)。共通表処理: [BaseConnector](../../../apps/core/base_connector.py)。
- UI宣言: [config.js](../../../apps/gui/config/config.js)のactions／forms。専用欄なしの引数は実装から補足。
- 共通仕様: [Connector契約](../../features/connectors.md)、[データ契約](../../features/data-contract.md)。
- 結果登録・template・loop・report: [WorkflowEngine](../../../apps/core/workflow_engine.py)。
- 調査Task: [TASK-053](../../tasks/done/TASK-053/TASK-053.md)。
- 未確認: 本Taskでは製品テスト・外部接続・OS入力・実ブラウザー・各保存先への書込を実行していない。環境依存の成否・性能は未検証。
- 更新時: 仕様と実装を再照合し、差異を記録する。実装観測だけを理由に現行仕様やTASK-048の決裁を書き換えない。
