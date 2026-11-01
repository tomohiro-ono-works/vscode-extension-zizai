# Python共通基盤の設計方針と了承範囲

判断記録日：2026-10-23（JST）。対象：[TASK-003 / #3](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/3)、[TASK-003-02 / #21](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/21)。

## 目的と根拠

本チャットの利用者回答と、[Python共通基盤の設計資料](../research/python-import/TASK-003-02.md)に対する了承を記録する。作業範囲・進捗・完了判定は担当Issueを正本とする。本書は製品仕様の一括置換、他チャットの判断履歴の削除、実装・導入・実機確認の完了を意味しない。

1. Pythonコネクタの用途への回答：

   > フォームにPythonコードを入力して実行する
   > なので、通常のPythonセルでよいと思ってます。

   Pythonは標準セルで扱い、専用コネクタ・フォーム・実行APIを設けない設計とする。CSV、Excel、DuckDB、BigQuery、Data Integration、Shellの専用6コネクタと通常Pythonに整理する。

2. 未設定時の実行への回答：

   > まず、フォームで値を設定するとPythonコードが生成されます。
   > なのでうまく設定しなかったらpythonが生成されないです。
   > 実行されたらPythonのコードが実行されるのでデフォルトの機能で問題ないです

   設定が成立したときに処理コードを生成し、その時点のセルsourceをJupyter標準機能で実行する。未設定用の例外コードや独自の実行制御を追加しない。既存の下書き編集中・確定NG時に確定済みsourceを維持する方針は、未設定状態で新規コードを生成しない条件と区別する。

3. 上記を反映した設計資料の提示後の回答：

   > OKです。つぎに進んでください。

   本資料に提示済みの設計方針を了承し、後続の具体化へ進む根拠とする。distribution `zizai-runtime`、import `zizai`、共通処理とコネクタを責務別の正本から1つの自作wheelへ収集する構成、選択カーネルへの手動導入を受け渡す。依存版・正式な個別シグネチャ等の未確定事項まで承認されたとは扱わない。

## 関連設計への整合

[PR #49の固定版](https://github.com/tomohiro-ono-works/vscode-extension-zizai/blob/40db82f55483f403c311bddea087ef3765e0ba1f/docs/research/development/TASK-006-01.md)のVSIX＋wheel、1自作wheel、root配布設定の案と対応する。

[PR #51の固定版](https://github.com/tomohiro-ono-works/vscode-extension-zizai/blob/9d55d98152c7cc85acf880499e3975ed28e9c5be/docs/research/contracts/TASK-005-03.md#contract-draft-20261023)には、別チャットでの未設定用ValueErrorの判断と、003-02向けの別命名候補が記録されている。これを同じ判断とみなさず、本チャットの具体的な回答・了承との差分を設計資料で明示する。契約側の例・定義・期待結果と、既存の「初回7コネクタ」記載は担当領域で整合する必要がある。今回、そのPR・現行仕様・他Issueを変更済みとは扱わない。

## 未確定のまま残すもの

- 採用アクションと正式なクラス・メソッド・引数・表型・戻り値・副作用。
- Python向け契約資産の形式・生成先・同期・陳腐化検出。
- 対応Python範囲、直接依存・推移依存の固定、ビルド版、実資産のlicense・元コードの利用許諾。
- 現行coding-rules／refactor-policyの未収録と、製品側の具体的な正本・更新経路・編集範囲。

対象部分の入力が揃った単位で後続計画を具体化する。製品コード・manifest・lockの作成、環境変更・依存導入・ビルド・実機実行・公開・Issue完了を、本記録の作成だけで許可済み・実施済みにしない。

<a id="save-file-name-20261030"></a>
## 2026-10-30：保存先フォームのファイル名は名前だけとする

003のフェーズ1照合中に、保存先フォームのファイル名欄へ絶対path等を入れると、別欄の保存先folderが使われない場合があることを説明し、「名前だけを受け付ける」か「pathも許可する」かを質問した。利用者の回答は **「名前だけを受け付ける（推奨）」**。

- 適用対象はCSV／Excel保存先のfile_name欄。folder欄と分離し、フォルダ成分・絶対path・drive指定を名前として扱わない。黙ってbasenameを抽出したりtrimして通したりしない。
- 名前欄の入力不備として検証する責務は004／005の個別定義・生成側へ渡す。通常Pythonの保存APIはoutput_pathへ完成したpath文字列を受け取るため、この引数を名前だけへ制限しない。coreのpath helperや新しい実行処理は追加しない。
- 本回答は名前欄の動作の判断。005のkernelPathJoin種別・schema版、002の生成・保存設計全体、製品実装／UI適合の承認・完了には広げない。[003の照合回答](../research/python-import/TASK-003-02.md#contract-response-20261030)とIssue #21へ対応付ける。
