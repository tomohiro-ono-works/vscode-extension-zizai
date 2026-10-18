# ChromeConnector — 入力・出力リファレンス

- ラベル: #領域/コネクタ
- 確認日: 2026-10-17（作業ツリーの静的読取り）
- 位置づけ: 現行実装の調査資料。Current Specificationではない。
- [索引・共通の読み方](README.md)／[新結果形式と承認状態](README.md#new-result-format)

## 概要

許可URLをローカルChromeへ非同期に渡す。Chrome実行ファイルの検出が必要。DOM操作や遷移完了待ちは担当しない。

## アクション一覧

| Action ID | 画面名 | 現在の戻り値 |
| --- | --- | --- |
| [open_in_chrome](#open_in_chrome) | Chrome でページを開く | DataFrame |

## 利用前提・共通境界

- 入り口: `execute(action, params, context)`。下記の入力例はparamsのみ。説明用の架空値であり、実行・外部接続による検証結果ではない。
- 出力例のdfは読みやすいrecords表現。実際の戻り値はDataFrameであり、JSON配列ではない。時刻・ID・path等は例示値。
- input_data／source_step_idを使う例は、必要な列を持つ前段結果がそのcontextキーにあることを前提とする。Engineへ保存するstep.output_variableも指定する。
- UI欄と実行側の条件・既定値は別。UIからの通常操作はUI値が渡るため、実行側省略値と一致するとは限らない。
- schemaの型・参照式は[共通データ契約](../../features/data-contract.md)を参照。schema適用後の値・列型は共通変換の影響を受ける。
- 未知actionは原則ValueError。依存・共通前提の検査が先に失敗する場合もある。

<a id="open_in_chrome"></a>
## open_in_chrome

用途: Chrome でページを開く。

### 入力

| 引数 | 型 | 実行側の条件・既定値 | UIの必須・既定値 | 意味・制約 |
| --- | --- | --- | --- | --- |
| `url` | str | 必須、前後空白を除去 | 必須、既定 指定なし | Web allowlistで許可されたURL。 |
| `output_var` | str | 任意 | 専用欄なし | 戻り値を指定contextキーへ追加するConnector側の別名。Engineのoutput_variableとは別設定。 |

context: 業務データを読まない。output_var指定時は受け取ったcontextへdfを保存。

### 戻り値

型: `pandas.DataFrame`。

| 列・項目 | 値の型 | 意味 |
| --- | --- | --- |
| `status` | str | success |
| `action` | str | open_in_chrome |
| `url` | str | 要求URL |
| `browser` | str | chrome |

後続での利用: 戻り値はEngineがstepのoutput_variableへ登録する。

### 使用例

入力（params）:

```json
{
  "url": "https://example.com"
}
```

出力の説明例:

```text
[ {"status":"success","action":"open_in_chrome","url":"https://example.com","browser":"chrome"} ]（1行df）
```

### エラー・副作用・制約

URL不足・許可外、Chrome未検出、プロセス起動失敗。ChromeへURLを非同期に渡す。成功は起動要求の受渡しまでで、ページ取得完了やredirect先の検証を示さない。

根拠: [chrome_connector.py](../../../apps/connectors/chrome_connector.py)の`execute`（確認時L16）、`open_in_chrome`（L22）。

## 新結果形式との関係

jsonの割当案。現在はstatus等の1行DataFrameを返す。

共通のresultType／result／meta、status・時刻・error等は[索引の新結果形式](README.md#new-result-format)と[最新のAction型割当](../../designs/TASK-048-action-result-design.md#result-type-allocation)を参照。新形式は製品未実装であり、本書の現在の戻り値へ既に付いているという意味ではない。

## 根拠・未確認事項

- 実装: [chrome_connector.py](../../../apps/connectors/chrome_connector.py)。共通表処理: [BaseConnector](../../../apps/core/base_connector.py)。
- UI宣言: [config.js](../../../apps/gui/config/config.js)のactions／forms。専用欄なしの引数は実装から補足。
- 共通仕様: [Connector契約](../../features/connectors.md)、[データ契約](../../features/data-contract.md)。
- 結果登録・template・loop・report: [WorkflowEngine](../../../apps/core/workflow_engine.py)。
- 調査Task: [TASK-053](../../tasks/done/TASK-053/TASK-053.md)。
- 未確認: 本Taskでは製品テスト・外部接続・OS入力・実ブラウザー・各保存先への書込を実行していない。環境依存の成否・性能は未検証。
- 更新時: 仕様と実装を再照合し、差異を記録する。実装観測だけを理由に現行仕様やTASK-048の決裁を書き換えない。
