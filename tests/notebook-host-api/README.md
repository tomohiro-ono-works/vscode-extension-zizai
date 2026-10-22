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

- Jupyter内部・VS Code内部モジュール、提案API、独自カーネル、独自Run All、実行サーバーは使用しない。標準セル実行・Run Allをユーザーが操作する。
- 公開APIで得られない実送信source・内部実行ID・カーネル停止完了は「観測不能」と記録する。ユーザーのボタン操作時刻と要約受信時刻も区別する。
- タブを閉じた事実、NotebookDocumentのclose通知、カーネルの停止は別の観測。D5のローカル遅延更新は対象オブジェクト・セル所属・close・最後のタブ閉鎖を照合する診断で、Jupyterの実行要求ではない。製品用の競合処理や原子性を保証するものではない。
- 参照比較のため閉じたNotebook／削除セルの参照をセッション中に保持する。これは診断用であり、製品の一時状態保持方式ではない。
- D6の時間には同期ログ採取の負荷を含む。送信回数・受信回数・版の差が一致すること、API1回がUndo1回になることは期待しない。性能の数値合格基準は未定。
- D5の手順は削除後にそのまま待機する条件。削除後15秒以内にUndoで同一セル参照を復元する複合条件は未検証で、ローカル遅延要求の安全性をその条件へ一般化しない。
