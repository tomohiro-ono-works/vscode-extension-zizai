# TASK-002-01 Windows Notebook管理API検証

このファイルは再利用する操作手順。結果・進捗・判定・残作業は [Issue #14](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/14) を正本とし、親 [#2](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/2) に要点を反映する。全ケースを一度にユーザーへ依頼しない。

## 分担と前提

エージェントが環境・依存・ビルド・起動・ログ収集・JSON比較・修正・結果記録を行う。ユーザーはVS CodeのUI操作と短い報告だけ行う。エージェントは毎回、確認内容、操作ウィンドウ、実在するコマンド等、短い番号付き操作、期待表示、報告例を示す。ユーザーの報告後、ログを確認してから次へ進む。

診断workspaceは `results/task-002-01/workspace/`、ウィンドウタイトルは `TASK-002-01 API診断`。下部ステータスに `TASK-002-01: 診断ログ記録中` が出る。F5起動設定は **TASK-002-01: Notebook Host API (DIAGNOSTIC)**。エージェントがCLIで開いた場合、ユーザーのF5は不要。

初回にJSONテキストとして表示された場合は、下記の **Open Diagnostic Case → D1-structure** を使う。このコマンドは公開Notebook APIで編集画面を明示して開く。Colabの利用状況収集の通知が出ている既存ウィンドウでは、まず通知右上の×を閉じる。これはJupyterの実行エラーではない。診断用の起動設定には `--disable-extension=google.colab` を指定し、CLI起動時も同じフラグを使う。既存の通常プロファイルや拡張のインストール状態は変更しない。

信頼確認が表示された場合は、今回生成した診断フォルダーのパスであることを確認して信頼する。実データのNotebookは開かない。D1〜D3とD6はカーネル実行不要。D4／D5では標準の「カーネルの選択」でエージェントが確認したPythonを選ぶ。追加インストールが要求されたら操作を止め、表示だけ報告する。

## 共通操作

- `Ctrl+Shift+P` → **TASK-002-01: Open Diagnostic Case** → 指定ケース。毎回新規の架空Notebookを作る。同じパスを再オープンするD2／D5ではこのコマンドを使わず、閉じたタブを `Ctrl+Shift+T` 等で開き直す。
- **TASK-002-01: Record Step** → 指定マーカー。前後の全観測Notebook、削除セルの保持参照、版、dirty等を記録する。マーカー通知を見て報告するだけでよい。
- Notebookのセル選択はコードをクリック後 `Esc` で編集から抜ける。セル移動は `Alt+↓`／`Alt+↑`、上下複製は `Shift+Alt+↓`／`Shift+Alt+↑`。これらはセルにフォーカスした状態で使う。source文字列が編集された場合は追加操作せず報告する。
- 保存は `Ctrl+S`。Undo／RedoはNotebookにフォーカスして `Ctrl+Z`／`Ctrl+Y`。操作単位ごとにマーカーを付ける。期待と異なっても自動で繰り返したり復旧しない。

## D1：構造変更

`D1-structure` はA・B・Cの3セル。各セルの診断metadataと所有外sentinelは異なる。操作は1種類ずつ案内する。

| 小単位 | UI操作 | マーカー | エージェントが照合すること |
| --- | --- | --- | --- |
| D1-0 | 初期表示を確認 | baseline | A/B/C、API metadata階層、URI・オブジェクト番号 |
| D1-1 | Aを下へ1セル移動 | D1-move-down | B/A/C、remove/addと最終所属・metadata・同一参照 |
| D1-2 | Aを上へ1セル移動 | D1-move-up | A/B/C、移動と削除を区別できる観測根拠 |
| D1-3 | Aを下に複製 | D1-duplicate-down | 新旧source・metadata保持／消失、URI・参照差 |
| D1-4 | 独立した新規ケースでBを上に複製 | D1-duplicate-up | 上方向のsource・metadata・参照差 |
| D1-5 | 独立ケースでセル選択状態のAをCtrl+C、Cを選択してCtrl+V | D1-copy-paste | セル貼付とテキスト貼付の区別、metadata・位置・参照 |
| D1-6 | 対象セルをセルの削除ボタンで削除 | D1-delete | 最終所属なし、index、TextDocument close、保持参照 |
| 各操作後 | Undoを1回、続いてRedoを1回 | undo / redo | 各段階のsource・metadata・参照対応。複製・貼付・削除も別々に記録 |

移動・複製・貼付・削除のUndo／Redoを省略しない。セル削除ボタンは対象セルのツールバーのごみ箱。画面にない場合はUIの「…」メニューを確認し、エージェントが実在する表示を特定して案内する。

最初の報告例：「D1の3セルが表示され、baseline記録済み」。次の報告例：「Aを1つ下へ移動でき、B/A/C。D1-move-down記録済み」。その都度エージェントがログを確認する。

## D2：metadataのみ更新・保存復元

1. 新規 `D2-save` を開きbaseline。
2. **TASK-002-01: D2 Update Metadata Only** を実行。source表示は不変、未保存表示を観察する。マーカーで記録。
3. `Ctrl+S` → saved。通常保存イベントで採取したJSONとAPIの外側metadata／内側metadata、所有外キー、sourceをエージェントが比較する。
4. タブを閉じて同じパスを再オープン → reopened。実際のAPIオブジェクトの同一／相違とdirty、保存値を比較する。タブ終了だけでNotebook close通知を受信したと扱わない。

## D3：source／metadata混在編集

**TASK-002-01: D3 Mixed Edit** の選択肢を、新規 `D3-mixed` ごとに1つずつ実行する。

| 選択肢 | 順序・意図 |
| --- | --- |
| source-first-success | 同一WorkspaceEditへ有効source、metadataの順で追加 |
| metadata-first-success | 有効metadata、sourceの順で追加 |
| source-first-failure | 有効sourceの後に、セル数+100の不正metadata対象 |
| metadata-first-failure | 有効metadataの後に、sourceと存在しない診断用ファイルのテキスト編集。後続テキストグループの準備を失敗させる |

実行直後の戻り値・例外・両データ・版を採取する。ユーザーは通知と表示sourceを報告し、ログ確認が済むまでUndoしない。その後Undo→undo、Redo→redoをそれぞれ1回ずつ案内する。falseや例外を変更なしと解釈しない。部分適用が再現しても、製品として混在編集に合格したことにはしない。

Undo/Redoではセル全体選択か本文編集かを記録する。source先行失敗で本文だけが適用された場合、NotebookへフォーカスしたUndoと、`notebook.cell.edit` または本文クリック後のUndoを同一条件にしない。D2の別プロセス再読込、D3の本文フォーカス条件は `recovery.cjs` でエージェントが実行でき、ユーザーへ同じ操作を重ねて依頼しない。

## D4：標準実行の観測

`D4-basic.ipynb` は環境版・成功・空セル・意図的例外の4セルを1回の標準Run Allで観測する補助Notebook。最後のValueErrorは期待するテスト結果。記録コマンドの選択ミスや複数Undoが混在した場合は、マーカー名だけで実操作を確定せず、APIイベントとユーザー報告を対応づける。既存ログで対応できる回はRecord Stepの操作を省略できる。

実行中のmetadata-settingとsource-changedを同じ実行中に順に行う場合は、個別条件を独立に行った結果と混同せず、変更時刻と終了要約の対応を複合条件として記録する。

まず `D4-environment` を標準セル▶で実行し、Python／ipykernel／jupyter_client版を標準出力と保存JSONから採取する。CLIのPythonと選択カーネルの一致はこの時点で判定する。

| 架空Notebook | 標準UIで行うこと | 追加観測 |
| --- | --- | --- |
| D4-success | セル▶ | 成功、要約trueと到着順 |
| D4-exception | セル▶ | Python例外の標準表示、要約false |
| D4-cancel | started出力後、標準の停止／割り込み | cancel-request-before/after、要約、終了出力を別記録 |
| D4-empty | 空セルの標準実行 | 実際の通知有無とsuccess undefined。無通知も記録 |
| D4-running-edit | started出力後、D4 Change Selected Cell→metadata-setting。別ケースでsource-changed | 設定変更／source変更の受信時刻・版と完了要約 |
| D4-queued-edit | Run All。blocker開始後、後続セルにsource-changed | 待機中の現在sourceと版、要約・出力。送信sourceは推測しない |
| D4-queued-editの別ケース | 待機中の後続セルへ標準実行を再要求 | 要求前後のマーカーと観測回数。UIで再要求できない場合も記録 |
| D4-nonempty-to-empty | started出力後、D4 Change Selected Cell→source-empty | 非空コードが開始した表示、終了時現在source、要約undefined等を別々に記録 |

各回、開始前後のexecution-request-before/after、完了後observation-completeと通常保存を案内する。長いセルは90秒待機し、UI操作の時間を確保する。操作が間に合わなかった場合はタイミング不足と記録し、理由を説明して新規ケースを用意する。successの期待値は静的所見との比較対象であり、実値のtrue／false／undefinedを上書きしない。カーネル停止完了を要約だけで判断しない。

## D5：削除・閉じる・再オープン

`D5-queued-delete`／`D5-running-delete`／`D5-queued-close`／`D5-running-close` を別々に用意する。

1. 標準Run Allまたはセル▶で対象を待機中／開始後にする。started等の表示、操作前のsource・版を記録する。
2. 対象セルを選択し **TASK-002-01: D5 Arm Delayed Local Update** を実行。これは15秒後の診断用metadata更新待機で、標準実行を代替しない。
3. D5-before-close-or-deleteを記録し、指定セルを削除、またはNotebookタブを閉じる。クローズ時に保存確認があれば、その選択と結果も記録する。
4. クローズの場合は同じパスを再オープンする。reopenedで記録。15秒後のlocal-delay.guard、古い参照、再オープン後のmetadataをエージェントが照合する。
5. 標準実行の遅延出力・要約の有無と到着対象を待ち、通常保存。必要な場合だけ標準割り込みをUIで案内する。

最後のタブ閉鎖時は診断の保留要求を無効にする。NotebookDocumentが閉じず同じ参照で再使用された場合も、その事実を記録する。公開編集APIにNotebook寿命を原子的に指定できることを保証する検証ではない。旧要求が観測範囲で適用されなかったことと、カーネル停止／製品方式の成立を分ける。

## D6：連続metadata更新

新規 `D6-burst` で **TASK-002-01: D6 Metadata Burst** を実行する。`existing-same-20`／`existing-change-20`／`new-same-20`／`new-change-20` を独立に行う。必要に応じて既存セル100回の2条件を追加測定する。sameは同じJSON値を再構成して送る。newはセル追加直後に同じ処理を行う。

送信ごとの戻り値・イベント数・Notebook版・dirty・時間・50ms周期のエージェント内タイマー遅延を記録する。受信数は内部操作数とは同一視しない。計測に同期ログの負荷を含める。

終了後、Undo→undo、Redo→redoを1回ずつ記録し、セル追加を含むまとまりと値の変化を確認する。必要なUndo回数の調査はログを見てから1回ずつ依頼する。通常保存→savedでJSONを確認する。ユーザーは操作中のもたつき・フリーズ等の有無を短く報告する。時間やUndo回数に独断の合格閾値を設けない。

## 判定の記録

エージェントが各小単位を合格／不合格／未実施／対象外に分け、Issueへ対象版・commitと差分hash・操作・期待・実際・証跡を対応付ける。B01〜B09等の静的所見の再現と、製品要件を満たすかは別欄にする。環境・タイミング・UI制限で必要な観測が得られなければ未実施または制約を明記し、必須確認が残る間はIssueを閉じない。Kiro・TASK-002-02以降・製品実装・正式契約・現行仕様の変更は対象外。
