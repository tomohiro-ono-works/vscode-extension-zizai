# TASK-002-01 Notebook管理APIの診断

製品から分離したWindows実機用プローブ。開始基準は `85358a0147fb49221c807f3acc6b78fc8f555c95`。
操作手順は [手動確認](../manual/TASK-002-01-notebook-host.md)、結果・残作業の正本は [Issue #14](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/14)、親は [#2](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/2)。TASK-001のF1〜F6とは別の検証。

## 配置と更新経路

- 本フォルダーの `extension.cjs`・`model.cjs`・`fixtures.cjs`・`package.json` が診断用ソースの正本。`prepare.mjs` が `dist/` へコピーする。外部由来のコピーや製品モジュールは含まない。
- `dist/build.local.json` は対象Git HEAD・未コミット状態・各診断ファイルのSHA-256を記録するローカル生成物。製品のビルドではない。
- 架空データは `fixtures.cjs` から `results/task-002-01/workspace/` へ生成する。準備の再実行で既存Notebookを上書きしない。UIのOpen Diagnostic Caseは毎回別名の新規Notebookを作る。
- `task00201Diagnostic` は診断限定キー。正式metadataキー・セルID・実行世代・更新方式を定めない。オブジェクト番号はExtension Hostプロセス内の参照対応を観測する番号であり、永続IDではない。
- `.vscode/launch.json` と `tasks.json` は本診断の入口だけ追加し、既存TASK-001設定を保持する。製品ソース・仕様・他Subtaskは変更しない。

## エージェントが実行する準備

共通ルール取り込み後の分類は [操作計画の検証経路と担当](../manual/TASK-002-01-notebook-host.md#検証経路と担当) を参照する。このフォルダーの公開API・標準コマンド直接呼び出しはAPI・結合テストで、UI自動テストや手動UIの代替ではない。特に `execution-save-followup-ui.cjs` は最初のカーネル選択支援の後をAPIで自動操作する入口であり、手動の編集・ごみ箱・タブ終了の代替として再起動しない。Playwrightの対象・開始方法・担当の合意前は新たなUI自動化を行わない。既存証跡の分析と単体・構文確認は、GUIを起動せず独立して行える。

`execution-save-followup.cjs` はD4の実行待ちsource変更＋同一セルへの標準再要求＋保存JSON、D5待機中close後の修正済み保存だけを採取する。以前の各ケース全体は繰り返さない。45秒で標準カーネル出力が得られなければ未実施として終了する。`execution-save-followup-ui.cjs` は同じ2条件について標準UI選択・最初の実行を10分待つ入口で、初回失敗を退避してから使う。結果は `execution-save-followup-result.local.json` とし、従来の `execution-auto-result.local.json` は上書きしない。セル置換でもfixtureの標準cell.idをAPI外側metadataへ渡す。

専用profile `task-002-01-execution-auto` に対して `code.cmd --verbose --new-window --wait --disable-workspace-trust --disable-extension=google.colab --user-data-dir=<profile絶対パス> --extensionDevelopmentPath=<dist絶対パス> --extensionTestsPath=<dist/execution-save-followup-ui.cjs絶対パス> <dist/save-followup.code-workspace絶対パス>` をエージェントが実行する。結果JSONの開始時刻と `kernelSelectionGate` を確認してから、タイトル「TASK-002-01 保存追加確認」のウィンドウ、`USER-kernel-bootstrap-20261024.ipynb`、`import sys, importlib.metadata as m, json` から始まるコード枠を案内する。ユーザー操作は必要な標準カーネル選択と最初の標準実行だけ。その後は自動で実行・変更・再要求・閉鎖・再オープン・保存するため、追加編集は依頼しない。

D6のGUI確認では、コマンドパレット操作・モード選択・更新・保存をユーザーへ依頼しない。エージェントが新規の `UI-D6-auto-*.ipynb` をD6 fixtureから作成し、固有user-data-dirで `TASK00201_UI_BURST=existing-change-20` を環境へ渡して通常の診断HostをCLI起動する。起動時処理はこのファイル名、1セル、診断label=D6-existing、初期burst=0を照合してから既存burstコマンドへ引数を渡す。公開WorkspaceEditで20回更新し、source不変・burst=20・保存trueを確認して `ui.preparation.complete` を記録する。カーネル・実行サーバー・外部コード実行口は追加しない。

エージェントはログで準備完了を確認してから、表示中の `fictional_value = 60` の行をクリックしてカーソルが出るかだけをユーザーへ案内する。この観測は更新・保存後のクリック応答であり、連続更新中の入力遅延を測定したとはしない。時間には同期ログ採取等の負荷を含み、数値の合格基準は決めない。GUIウィンドウを保持する通常起動なので、extensionTestsPathの終了で確認画面が消える方式ではない。

標準カーネルの選択はCLIだけで完結するとは扱わない。`execution-auto.cjs` の最初の環境確認は10分の待機上限を持ち、自動試験ウィンドウ内でのカーネル選択・必要な場合の標準▶実行後に続行する。選択だけで既に終了した実行要求が再実行されるとは案内しない。画面に存在しない「環境セル」等の名称を操作対象にせず、ファイル名と `import sys, importlib.metadata as m, json` から始まるコード枠を示す。

現在の入口は、ユーザーが標準カーネルを選択した架空の `USER-kernel-bootstrap-20261024.ipynb` と同じパスを使う。開始時にコピーを保存し、条件ごとのセル置換は公開 `NotebookEdit.replaceCells` で行う。置換はfixture準備でありD5の削除操作ではない。各条件の前後・object番号・時刻は結果の `fixtureSetup` と `results` で区別する。同じNotebook URI／APIオブジェクトが条件間で再利用され得るため、独立ファイルの結果とは扱わない。実行コマンドへは宣言された引数としてURI・セル範囲を明示し、D5のセル削除は公開 `NotebookEdit.deleteCells` を使う。標準削除ボタンのUI検証には流用しない。

再オープン時は `openNotebookDocument` の戻り値と `showNotebookDocument` が返したeditorの `notebook` を別々に記録する。2026-10-24の試行では前者が旧参照を返す間に旧documentがclose、新documentがopenした。旧参照への最終saveでrunnerが失敗したため、保存にはeditorが実際に保持するdocumentを使うよう修正した。既に採れたD4・D5削除・待機中closeの証跡は保持する。`running-close.cjs` は残る開始後closeだけを選んで同じrunnerを起動する。

`execution-auto.cjs` はD4の実行中metadata変更／source変更を独立した2実行、D5の待機中／開始後×削除／タブcloseの4条件として、標準 `notebook.cell.execute`／`notebook.execute` コマンドと公開APIで観測する入口。ユーザーからコマンドベース検証の継続依頼を受けて用意した。独自Run All・カーネル・実行サーバーは含まない。自動操作用の架空コピーだけ待機20秒へ変更し、手動用90秒と区別する。

Jupyter／Python拡張を有効にした別user-data-dirを使う（`--disable-extensions` は使わない）。その専用profileの `User/settings.json` で `python.defaultInterpreterPath` を `C:\\Python314\\python.exe`、`notebook.confirmDeleteRunningCell` を `false` に設定する。後者は自動削除時の確認ダイアログを省く診断条件であり、一般ユーザー設定を変更しない。更新・拡張の自動更新を停止する専用設定も使い、実際の値を結果へ記録する。実行中の保存変更は削除／タブclose前にも保存する。起動後のカーネル選択が必要なら自動試験は開始出力の待機上限で失敗として記録し、選択済みとは推測しない。

起動はインストール済み `code.cmd` に `--new-window --wait --disable-workspace-trust --disable-extension=google.colab --user-data-dir <専用profile> --extensionDevelopmentPath <dist絶対パス> --extensionTestsPath <dist/execution-auto.cjs絶対パス> <workspace/USER-kernel-bootstrap-20261024.ipynb絶対パス>` を渡す。`prepare` はこの架空ファイルを未作成の場合だけ生成する。CLIのextensionTestsPath実行前は同じ専用profileの通常ウィンドウを閉じる。`execution-auto-result.local.json` の生成時刻・status・各条件の実値を確認する。2026-10-24の初回起動はVS Code自身の更新mutexで拒否され、結果ファイルが生成されなかった。CLI終了コード0を実行済みとは扱わない。その後の実行・失敗・修正の証跡は調査資料から参照できる。

`recovery.cjs` は既存D2保存ファイルを新しいExtension Hostプロセスで読み直し、D3のsource先行失敗後を `notebook.cell.edit` でセル本文へフォーカスしてUndo/Redoする関連確認。既存の `automated-result.local.json` と対応する架空ファイルが必要。`--extensionTestsPath` をこの入口へ変更し、別user-data-dirを使う。`recovery-result.local.json` に以前のログ・新しいセッション・戻り値・実データを対応づける。

`structure-ids.cjs` はD1削除の不一致について、標準nbformat `cell.id` を初期JSONへ付ける比較条件。正式セル識別方式の提案ではない。2026-10-24の確認では削除後のUndoでセル数2のまま失敗し、ID補完だけでは原因を説明できなかった。初期IDなしの過去2試行も保持し、原因未確定とする。診断ランナーは各操作後に状態を保存してから期待値を検証する。後から追加した保存処理を過去の実行済みコードと混同しない。

Node.jsのみで準備でき、npm依存の追加・インストールは不要。

`automated.cjs` はD2・D3・D6、`structure.cjs` はD1の上方向複製・標準コピー貼付・削除とUndo/Redoを公開API／標準コマンドで観測する実VS Code用テスト入口。実行方法は下記スモークと同じ `--extensionTestsPath` を該当ファイルへ変更する。`structure-delete.cjs` は削除条件だけの関連再確認。手動Notebookと分離したAUTO名の架空ファイル、別user-data-dirを使う。

自動確認は各 `results/task-002-01/*-result.local.json` とrawLog参照へ記録する。`completed` はランナーの完走であり、全ケース合格ではない。D3はfalse後の部分適用とUndoの実値を、D6は性能閾値未定・20msの観測待ちを含む計測条件を保持する。削除Redoはセル数の期待不一致を検出し、フォーカス再明示後も未解決。これを診断側の期待に合わせて成功へ書き換えない。

```powershell
node tests/notebook-host-api/prepare.mjs
node --test tests/notebook-host-api/model.test.cjs
```

`prepare` はCommonJSの構文確認、診断拡張の配置、テストNotebookと専用workspaceの生成を行う。Python既定パスはこのWindows環境の `C:\Python314\python.exe`。他環境ではエージェントが `TASK00201_PYTHON` を指定して準備する。カーネルはユーザーが標準UIで選択し、選択された実カーネルの版はD4-environmentで確認する。CLIで見つかったPythonと選択カーネルを同一視しない。

実VS CodeのCLIに `--extensionDevelopmentPath=<dist絶対パス>`、`--extensionTestsPath=<dist/smoke.cjs絶対パス>`、診断専用 `--user-data-dir` を渡すと、公開APIによるスモーク確認を実施できる。`smoke-result.local.json` の更新日時と `status` を確認する。CLI起動コマンドの終了コード0だけでは試験成功を示さない。スモーク時の `--disable-extensions` は導入済み拡張を無効にするため、Jupyter実行の確認には使わない。

## 証跡

`logs/task-002-01/<UTC日時>-<pid>/events.jsonl` に、連番・UTC時刻・単調経過時間・操作マーカー・公開API受信値を同期保存する。通常保存の際にその `.ipynb` のコピー・SHA-256・JSONを同じセッションへ記録する。対象は生成された診断workspace配下のNotebookに限定する。

```powershell
node tests/notebook-host-api/inspect.mjs
```

エージェントが実行し、最新セッションの要約を `summary.local.json` へ保存する。引数でセッションのディレクトリ名を指定可能。ユーザーへログ整理やコマンド入力を依頼しない。共有時はエージェントが架空データであることを確認し、ローカルパスを除いた必要な証跡だけ `docs/research/notebook-host/evidence/` へ残す。

`undefined` はJSON上で `{"$undefined":true}` として明示する。`false`、省略、空オブジェクトへ変換しない。イベントのoptionalフィールドはキーの列挙結果と値を両方残す。キーが存在して値がundefinedの場合もある。sourceは受信時の現在値であり、送信sourceではない。出力イベントではMIME・バイト数・hashを記録し、出力の本文は標準Notebookと保存JSONに残す。

## 観測上の限界

2026-10-25 JSTのD1比較は `structure-focus.cjs`。先頭セル・`notebook.focusTop`／`notebook.cell.quitEdit`・各300ms待機を共通にし、初期cell.idなし／ありを比較する。導入済み拡張はCLIの `--disable-extensions` で無効、内蔵ipynbと診断拡張だけの編集条件。IDなしは3→2→3→3、ありは3→2→3→2を観測した。以前のユーザーBセル・Ctrl+Y条件や1.143.0の比較とは分ける。全般的なRedo不具合の原因断定には使わない。

初期fixtureはnbformat_minor=5なのにcell.idを欠いていた。[nbformat 4.5の要件](https://nbformat.readthedocs.io/en/latest/format_description.html#cell-ids)に合わせ、今後の生成Notebookには標準cell.idを付ける。製品の永続識別方式は定めない。過去ファイルと観測は上書きせず、IDなし比較だけ明示的に削除する。D6の今回のUI観測も旧IDなしfixture条件として残し、クリック応答から更新中の遅延や正常形式全般の性能を保証しない。

- Jupyter内部・VS Code内部モジュール、提案API、独自カーネル、独自Run All、実行サーバーは使用しない。標準セル実行・Run Allをユーザーが操作する。
- 公開APIで得られない実送信source・内部実行ID・カーネル停止完了は「観測不能」と記録する。ユーザーのボタン操作時刻と要約受信時刻も区別する。
- タブを閉じた事実、NotebookDocumentのclose通知、カーネルの停止は別の観測。D5のローカル遅延更新は対象オブジェクト・セル所属・close・最後のタブ閉鎖を照合する診断で、Jupyterの実行要求ではない。製品用の競合処理や原子性を保証するものではない。
- 参照比較のため閉じたNotebook／削除セルの参照をセッション中に保持する。これは診断用であり、製品の一時状態保持方式ではない。
- D6の時間には同期ログ採取の負荷を含む。送信回数・受信回数・版の差が一致すること、API1回がUndo1回になることは期待しない。性能の数値合格基準は未定。
- D5の手順は削除後にそのまま待機する条件。削除後15秒以内にUndoで同一セル参照を復元する複合条件は未検証で、ローカル遅延要求の安全性をその条件へ一般化しない。
