> **注意：別アプリの参考資料です。**
> 本資料は別アプリの仕様・実装に基づいており、今回開発する VS Code 拡張機能の仕様・実装を示すものではありません。
> 記載されたコネクタの動作、入出力、実行方式、Task・承認情報は、本プロジェクトへの適用が未確定です。採用する内容は、本プロジェクト用に設計・検証してから反映します。

# コネクタ別の入力・出力リファレンス

- ラベル: #領域/コネクタ, #領域/エンジン
- 確認日: 2026-10-17（作業ツリーの静的読取り）
- 位置づけ: 現行実装の調査資料。Current Specificationではない。
- 対象: UIで選択できる12コネクタ・39アクション。BaseConnectorと内部previewはアクション一覧の対象外。
- 調査Task: [TASK-053](../../tasks/done/TASK-053/TASK-053.md)

## コネクタ一覧

| コネクタ | 件数 | 用途 |
| --- | --- | --- |
| [BQConnector](bigquery.md) | 3 | BigQueryのSQL実行とテーブルへのデータロード |
| [DuckConnector](duckdb.md) | 4 | ローカルDuckDBファイルの作成、SQL実行、表データの保存 |
| [ExcelConnector](excel.md) | 3 | Excelブックの通常読込・範囲読込・出力 |
| [CSVConnector](csv.md) | 2 | CSV／TSV等の表データの読込・出力 |
| [PythonConnector](python.md) | 1 | 選択したPython環境の子プロセスでスクリプトのmain()を実行する |
| [DataintegrationConnector](dataintegration.md) | 2 | 前段の表データにRENAMEリストと列名クレンジング、行フィルターを適用する |
| [VectorConnector](vector.md) | 2 | 埋め込みモデルとFAISS／DuckDBを使うベクトルDB構築・検索 |
| [ShellConnector](shell.md) | 1 | Windows BATをshell=Trueで実行する |
| [SeleniumConnector](selenium.md) | 5 | SeleniumのChromeセッションを保持し、遷移・DOM操作・取得・待機・撮影を行う |
| [ChromeConnector](chrome.md) | 1 | 許可URLをローカルChromeへ非同期に渡す |
| [WindowsConnector](windows.md) | 10 | 変数定義、ファイル操作、検索、OS入力、待機、画面上のloop_tasksを扱う |
| [PlotlyConnector](plotly.md) | 5 | 前段の表から5種類のグラフを作成し、ファイルへ保存する |

## 読み方・共通の入口

```python
result = connector.execute(action, params, context)
```

- action: Action IDの文字列。例: read_csv。
- params: アクション固有の引数辞書。保存flowではsteps[].params。
- context: 前段結果、開始変数、実行内部情報を持つ辞書。全キーが業務入力という意味ではない。
- result: 現在はDataFrame・文字列・list・scalar・None等。共通statusを持つ包装はまだない。失敗は基本的に例外でEngineへ伝播する。一部操作の成功表にはstatus等が列として入る。
- 各資料の入力表は実行側で受け取る型・条件とUI宣言を併記。UIでの必須指定、実行側の省略時既定値、実行側で読まないUI項目を区別する。
- 使用例は説明用の架空値。dfの出力例はrecords表現であり、実際の戻り値をJSON配列へ変更した意味ではない。日時・ID・処理件数・pathも実測値ではない。
- Current Specificationは[コネクタ契約](../../features/connectors.md)と[データ契約](../../features/data-contract.md)。実装との不一致は各資料へ記録し、仕様を暗黙更新しない。

### 前段データの参照と戻り値の登録

```json
{
  "step_id": "step2",
  "connector": "CSVConnector",
  "action": "write_csv",
  "params": {
    "input_data": "step1",
    "output_folder": "outputs",
    "file_name": "items.csv"
  },
  "output_variable": "step2"
}
```

- 前提: context["step1"]へ前段の有効な表を登録済みで、outputsフォルダが存在する。
- input_data等のreference-only引数は裸のcontextキー。{{step1}}等のwrapperやnested参照を受理しない。[現行参照契約](../../features/data-contract.md#reference-expressions)
- step_idとoutput_variableは区別。Engineの結果登録先はoutput_variableであり、step_idだけで必ず同名contextキーへ保存されると解釈しない。
- 通常templateの{{step1.field}}は現行ではdfの先頭行の列等を取得する。DataFrameのschemaはattrs["ziz_schema"]。列単位のorigin_name／new_name／description／ziz_datatypeは[データ契約](../../features/data-contract.md#schema-item)を参照。
- 現行Engineのreportにもstatus／result／error等がある。ただしreportは実行報告であり、Connectorが返すraw resultや、以下の新しいステップ結果形式と同一ではない。[現行実行報告](../../features/data-contract.md#execution-report)

<a id="new-result-format"></a>
## 新しいステップ結果形式の確認

ステータス等を含む共通の保持形式は、TASK-048のresultType／result／meta。保存済み.zizdのstep設定ではなく、実行時に保持するstep結果の設計。製品Source・Current Specificationへは未反映。

正本となる設計・決裁:

- [TASK-048の現在の承認・残作業](../../tasks/active/TASK-048/TASK-048.md#approval)
- [resultType／result／metaの概念](../../designs/TASK-048-step-result-requirements.md#result-envelope-v2)
- [共通meta9項目](../../designs/TASK-048-action-result-design.md#common-meta-proposal)、[承認048-00-20261010-05](../../tasks/active/TASK-048/approval-log.md#048-00-20261010-05)
- [全39Actionの最新型割当](../../designs/TASK-048-action-result-design.md#result-type-allocation)

### 外側の構造

| 項目 | 内容 | 状態・注意 |
| --- | --- | --- |
| resultType | dataframe／jsonで成果の保持形式を示す | 最新設計。成功／失敗の分類ではない。Action別詳細schemaは未確定部分あり |
| result | 処理成果。DataFrame、file情報、取得値、辞書、list等 | result／metaの名称は決定済み。表以外の成果を一律metaへ移さない |
| meta | 実行識別・状態・時刻・エラーとAction固有の実行情報 | 共通9項目の採用は承認済み。詳細分類・追加項目等は後続設計 |

dataframeは内部のpandas.DataFrameを保持し、包装だけのためにrows／schemaへ分解・deep copyしない。jsonもJSON文字列ではなく、正規化したdict／list／scalar／Noneを保持する設計。画面・通信のserializationは別の境界。

### 共通metaの9項目

以下は承認済みの共通metaの要約。ID生成方式、errorコードの分類・既存例外との対応、キャンセル情報等の詳細は別途設計する。更新時はリンク先の設計・決裁を確認する。

| 項目 | 意味 |
| --- | --- |
| run_id | フロー実行全体の識別子 |
| execution_id | step実行1回の識別子。loopや再実行でも区別 |
| step_id | フロー上のstep識別子 |
| connector | 実行Connector |
| action | 実行Action |
| status | 完了状態。success／error／cancelled。キャンセル情報の詳細は別途 |
| started_at | step処理開始。UTC日時文字列 |
| finished_at | step処理終了。UTC日時文字列 |
| error | 成功時null、失敗時code／messageのobject。コード分類・例外対応は別途 |

表取得の概念例（Python。dfは取得したDataFrame、IDは架空値）:

```python
{
    "resultType": "dataframe",
    "result": df,
    "meta": {
        "run_id": "run_example",
        "execution_id": "execution_example",
        "step_id": "step1",
        "connector": "CSVConnector",
        "action": "read_csv",
        "status": "success",
        "started_at": "2026-10-17T01:00:00Z",
        "finished_at": "2026-10-17T01:00:01Z",
        "error": None,
    },
}
```

file出力ではresultにfile_path／rows_written等、metaに実行状態等を置く案。これらのAction固有の項目名・取得範囲は最新型割当の評価対象であり、この例から全Actionの必須キーを増やさない。

### 決まっている振る舞いと残る詳細

| 論点 | 確認した状態 |
| --- | --- |
| 成果なし成功 | json＋null、meta.status=success。0行dfとは区別。共通6点として承認済み |
| 失敗 | 全Actionをjson形式で記録し、meta.status／errorへ保持。errorはcode／messageのobjectを採用済み。失敗時のresult=null、コード分類・キャンセル詳細は設計対象 |
| 未取得情報 | 定めた項目を残してnull。0件・空文字で未知を隠さない。承認済み |
| 不足参照 | 存在しない列・key・範囲外位置はエラー。既存keyのnull値とは区別。承認済み |
| 再実行失敗 | 今回の失敗を最新とし、前回成功を履歴として区別。保持方式・表示の詳細は未確定 |
| SQL | 最終実行文がSELECTの場合だけdf。その他はjson。対象・処理件数はresult、Job ID・SQL種類・状態はmeta。追加件数照会やRETURNING行保持はしない。承認済み、Action別の詳細は設計中 |
| Python | 実行前にdf／json選択。既定df。型不一致をエラーとし自動変換しない。承認済み、UI・保存項目・子processの詳細は未確定 |
| JSON正規化 | Ownerの選定委任に基づく規則を設計へ記録。日時・Decimal・大整数・欠損等の表現を定義。製品未実装 |
| browser_ref | JSONのresultから参照1値を後続へ渡す方式を承認。flow run内限定、手動発行は10分、失効時エラー等は052で承認。具体接続方式・対象・詳細schemaは別途 |

browser_refでは、参照値はresult.browser_ref、有効期限はmeta.browser_ref_expires_at（UTC日時）へ返す承認済み設計。手動stepは発行から10分で、操作による延長なし。接続用stepを再実行すると新しい参照を発行する。期限切れはmeta.status=error、meta.error.code=BROWSER_REF_EXPIRED。flow全体の実行は終了時失効のため固定日時の期限はnull。これらは共通meta9項目へ全Action共通の必須項目を増やす意味ではない。

根拠: [共通6点の決裁](../../tasks/active/TASK-048/approval-log.md#048-00-20261010-04)、[SQL方針](../../designs/TASK-048-action-result-design.md#sql-select-policy)、[Python型選択](../../designs/TASK-048-action-result-design.md#output-type-selection)、[JSON表現](../../designs/TASK-048-action-result-design.md#json-value-proposal)、[browser_ref](../../designs/TASK-048-action-result-design.md#selenium-json-reference)、[052の寿命承認](../../tasks/active/TASK-052/TASK-052.md#052-00-20261010-02)。

### 参照記法と実装開始条件

- 新しい明示参照は{{step1.result}}／{{step1.result[0]["価格"]}}／{{step2.meta.status}}等。記法は承認済み、現行parserで使えるという意味ではない。[明示参照設計](../../designs/TASK-048-action-result-design.md#explicit-references)
- 全体の包装・共通metaの採用を、各Connectorの詳細schema・error分類・履歴方式まで確定した承認と解釈しない。
- 現行のresult.metaという業務列・JSON keyと外側metaは別。新結果形式を既存の表へ暗黙に追加しない。
- 製品実装にはTASK-047の実際の初期リリース・完了根拠、共通要件の承認、仕様変更を含む後続Taskの明示範囲が必要。今回の資料作成では開始条件を変更しない。[TASK-048の制約](../../tasks/active/TASK-048/TASK-048.md#constraints)
- TASK-048の後段AR-01〜39は古い比較初案。最新RT割当・後続決裁を優先し、file成果を一律metaへ移す案やsessionをmetaへ置く案を最新契約として転記しない。

## 調査方法・更新時の確認

- 読取り対象: [UIカタログ](../../../apps/gui/config/config.js)、各Connector、[BaseConnector](../../../apps/core/base_connector.py)、[WorkflowEngine](../../../apps/core/workflow_engine.py)、関連仕様とTASK-048／052の決裁。
- 調査範囲: dispatch、入力取得、出力構築、context参照、関連helperを静的に確認。Action集合と文書の網羅性・相対リンク・アンカーを検査。
- 未実施: 製品の実行テスト、外部接続、課金、OS入力、実ブラウザー、モデル取得・実出力ファイル作成。本書を動作試験済みの保証として使わない。
- 更新時: UIの追加・変更と実行側のparams／戻り値を照合。現行仕様との差異や未確認事項は明記。新設計は既存の正本へリンクし、この調査資料から独自に確定しない。
