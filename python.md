# PythonConnector — 入力・出力リファレンス

- ラベル: #領域/コネクタ
- 確認日: 2026-10-17（作業ツリーの静的読取り）
- 位置づけ: 現行実装の調査資料。Current Specificationではない。
- [索引・共通の読み方](README.md)／[新結果形式と承認状態](README.md#new-result-format)

## 概要

選択したPython環境の子プロセスでスクリプトのmain()を実行する。wrapperがpandasをimportするため子環境にもpandasが必要。

## アクション一覧

| Action ID | 画面名 | 現在の戻り値 |
| --- | --- | --- |
| [execute_python](#execute_python) | Python実行 | DataFrame / scalar / None / str |

## 利用前提・共通境界

- 入り口: `execute(action, params, context)`。下記の入力例はparamsのみ。説明用の架空値であり、実行・外部接続による検証結果ではない。
- 出力例のdfは読みやすいrecords表現。実際の戻り値はDataFrameであり、JSON配列ではない。時刻・ID・path等は例示値。
- input_data／source_step_idを使う例は、必要な列を持つ前段結果がそのcontextキーにあることを前提とする。Engineへ保存するstep.output_variableも指定する。
- UI欄と実行側の条件・既定値は別。UIからの通常操作はUI値が渡るため、実行側省略値と一致するとは限らない。
- schemaの型・参照式は[共通データ契約](../../features/data-contract.md)を参照。schema適用後の値・列型は共通変換の影響を受ける。
- 未知actionは原則ValueError。依存・共通前提の検査が先に失敗する場合もある。

<a id="execute_python"></a>
## execute_python

用途: Python実行。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `env_path` | str | 省略時default | 必須、既定 "defult" | default／defult／system／空値は現在のsys.executable。Python実行file、仮想環境folder、PATH上のコマンドも可。 UI候補: ["defult","venv1","venv2"]。 |
| `script` | str | 必須 | 必須、既定 "def main():\n    output = None\n    return output" | 引数なしmain()を定義するPythonコード。 |

context: execute_pythonはcontextを受け取るが、wrapperのmain()へ自動で引数・前段dfを渡さない。通常文字列templateの解決はEngine側。

### 戻り値

型: `DataFrame / JSON互換scalar / None / str`。main()のdfはrecordsへ変換してJSONで親へ渡し、親はlist／dictをdfへ変換。scalar・Noneはそのまま。dfの元index・attrs・dtypeをそのまま保持する境界ではなく、非JSON値はdefault=strで文字列化する。

markerがないstdoutは全体JSONの復元を試し、JSONでなければ文字列。stdout自体が空なら成功message文字列。通常のwrapperはmarkerを出す。

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "env_path": "default",
  "script": "def main():\n    return [{\"id\": 1, \"name\": \"sample\"}]"
}
```

出力の説明例:

```text
[ {"id":1,"name":"sample"} ]（親で復元したdfのrecords表現）
```

### エラー・副作用・制約

script不足、実行環境不在、mainなし、子process異常終了、JSON復元エラー。任意Pythonを実行し一時scriptを作成・finallyで削除する。

UIのenv_path既定はdefult。新設計のoutput型選択は現行paramsには存在しない。

根拠: [python_connector.py](../../../apps/connectors/python_connector.py)の`execute`（確認時L18）、`execute_python`（L83）。

## 新結果形式との関係

実行前にdf／jsonを選択し、既定はdf。型不一致はエラー、自動変換なしを承認済み。設定項目名・UI・子プロセス境界は未確定。

共通のresultType／result／meta、status・時刻・error等は[索引の新結果形式](README.md#new-result-format)と[最新のAction型割当](../../designs/TASK-048-action-result-design.md#result-type-allocation)を参照。新形式は製品未実装であり、本書の現在の戻り値へ既に付いているという意味ではない。

## 根拠・未確認事項

- 実装: [python_connector.py](../../../apps/connectors/python_connector.py)。共通表処理: [BaseConnector](../../../apps/core/base_connector.py)。
- UI宣言: [config.js](../../../apps/gui/config/config.js)のactions／forms。専用欄なしの引数は実装から補足。
- 共通仕様: [Connector契約](../../features/connectors.md)、[データ契約](../../features/data-contract.md)。
- 結果登録・template・loop・report: [WorkflowEngine](../../../apps/core/workflow_engine.py)。
- 調査Task: [TASK-053](../../tasks/done/TASK-053/TASK-053.md)。
- 未確認: 本Taskでは製品テスト・外部接続・OS入力・実ブラウザー・各保存先への書込を実行していない。環境依存の成否・性能は未検証。
- 更新時: 仕様と実装を再照合し、差異を記録する。実装観測だけを理由に現行仕様やTASK-048の決裁を書き換えない。
