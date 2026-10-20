# TASK-001-01 言語選択の隣の選択UI（試作）

更新日：2026-10-20。**セル下部の表示・選択・初期化非表示は実機確認済み。起動時のDisposableStoreエラーは再発し、起点の特定は継続中。**

利用者の意図はセル右下の言語選択の隣への配置だった。先行版の右上セルツールバーとは位置が異なり、その実機合格を今回へ流用しない。利用者の「実装し直してテストの準備」と起動エラー原因調査の依頼によりTASK-001-01を再開。Kiroは引き続き対象外、標準Python実行の追加テストは後回し、本体・他Subtaskは未着手。

## 今回の試作と標準API

- 正本：`tests/notebook-ui-gate/statusbar.cjs`、`statusbar.package.json`、共有の `toolbar-state.cjs`／`role.cjs`。生成物はGit無視対象の `dist/statusbar/`。試作0.0.3、拡張ID `zizai-lab.task-001-01-probe`。既存の三方式は比較用の履歴として保持。
- `notebooks.registerNotebookCellStatusBarItemProvider` と `NotebookCellStatusBarItem` の右寄せで、言語選択と同じセル下部に `Zizai: 通常Python ▾` を寄与する。選択後は表示ラベルを更新する。
- クリック時は標準 `window.showQuickPick` を開く。**一覧は画面上部に出る。セルのボタン直下へ展開するドロップダウンではない。** 公開APIはセルステータスバー項目へ独自のアンカー付きメニューを付ける機能を提供しない。
- `priority = -Number.MAX_SAFE_INTEGER + 2`。対象版の言語選択は `-Number.MAX_SAFE_INTEGER`。言語選択の左側を狙う。他拡張・言語検出ヒント・幅によって厳密な隣接は保証できず実機で判定する。VS Code本体やDOMは上書きしない。
- `notebook.showCellStatusBar = visible` が必要。`hidden` や `visibleAfterExecute` では実行前表示を満たさない。試作用workspaceだけに `visible` を設定し、利用者のグローバル設定は変更しない。
- fixture内の通常Pythonセル／処理セルだけを対象にし、初期化セルでは返却項目なし。選択はHostメモリのみ。source・metadata・output・言語は変更せずPythonも実行しない。Notebookを閉じると選択を破棄する。正式なセル識別・保存契約は未実装。
- HTML／Renderer／試験的API／npm依存／独自カーネルなし。OutputChannelは作らず、診断はconsoleと明示操作で開くJSONレポートへ出す。

## 対象版と根拠

調査対象はVS Code **1.142.0**、commit `d956e8a6ac5d904486557eea07e1d6bd62a4d36f`。最低宣言 `^1.105.0` は旧試作と同じで、範囲内の全版を検証した意味ではない。実機想定は前回と同じWindows／Python拡張2026.10.0／Jupyter拡張2025.9.1。カーネル不要。Python 3.12.13は利用者の想定で、実機取得値ではない。

- [標準API定義](https://github.com/microsoft/vscode/blob/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/src/vscode-dts/vscode.d.ts)：`NotebookCellStatusBarItemProvider`、Right、priority、command、showQuickPick。
- [言語選択のprovider](https://github.com/microsoft/vscode/blob/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/src/vs/workbench/contrib/notebook/browser/contrib/cellStatusBar/statusBarProviders.ts)：セル言語表示とpriority。
- [セル下部の描画](https://github.com/microsoft/vscode/blob/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/src/vs/workbench/contrib/notebook/browser/view/cellParts/cellStatusPart.ts)：priority順と右寄せ項目の配置。
- [設定の定義](https://github.com/microsoft/vscode/blob/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/src/vs/workbench/contrib/notebook/browser/notebook.contribution.ts)：showCellStatusBarの三値、既定visible。

## 起動時のエラー調査

既存の会話ログを使用した。ログ再送を求めず、警告とエラーを分けて調べた。

| 症状 | 確認できた原因・経路 | 未確定な部分 |
| --- | --- | --- |
| DEP0169 `url.parse()` | Nodeの旧URL解析APIに対する非推奨警告。クラウドのNode 24.19.0でも `node --trace-deprecation -e "require('node:url').parse('https://example.invalid')"` で同文を再現。新旧試作に `url.parse()` 呼出しはない | VS Code／同梱依存／他拡張のどの呼出しが起点かは、受領ログに呼出元stackがなく特定不可。警告を起動失敗原因と断定しない |
| DEP0040 `punycode` | 新たに受領したNode組み込みpunycodeの非推奨警告。新版のソースにはimport／requireなし | 呼出元stackなし。Nodeのどの依存元かは未特定。DEP0169やDisposableStoreとの因果関係も未確認 |
| disposed DisposableStoreへの追加 | 受領stackの `doCreateOutputChannel` と対象版ソースが対応。OutputChannelは内部でディレクトリ作成・登録をawaitし、その後storeへlogger等をaddする。作成完了前にOutputChannelをdisposeすると、破棄済みstoreへaddする競合が起き得る | 対象拡張名・channel名・dispose時点は受領stackにない。前試作もOutputChannelを作るが、他拡張も使う。利用者の新版実機でも同文・同stackが再発。競合の起点は未特定、解消していない |

根拠：[extHostOutput.ts](https://github.com/microsoft/vscode/blob/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/src/vs/workbench/api/common/extHostOutput.ts) のcreateOutputChannel／doCreateOutputChannel／createExtHostOutputChannelと、[lifecycle.ts](https://github.com/microsoft/vscode/blob/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/src/vs/base/common/lifecycle.ts) のDisposableStore.add。後者はこの文を `console.warn(Error.stack)` で出す。ログのErrorという表示だけで拡張適用失敗やNotebook非表示の原因とは確定できない。実際に利用者はその後Notebookを開けている。

今回の試作ではOutputChannel作成経路を使用しない。さらに終了後の非同期選択結果を破棄する。これは試作の依存と終了時動作の整理であり、VS Code内部の競合そのものを修正した意味ではない。別プロセス／他拡張の警告が消える保証もしない。診断起動設定と比較手順は [手動手順](../../../tests/manual/TASK-001-01-statusbar.md#エラーが再発した場合だけ行う診断) に記載。

## 2026-10-20の実機結果

利用者の画面と「問題なく変更できました」の報告、および17:45〜17:50 JST（08:45〜08:50 UTC）の [受領イベント抜粋](evidence/2026-10-20-statusbar.jsonl) を照合した。抜粋は投稿ログ内の試作JSONイベント4件だけを値を変えずJSONL化し、個人パス・kernel識別子・他拡張のログは含めない。原文全体は会話を参照。

- Windows／VS Code 1.142.0／Host Node v24.21.0／試作0.0.3／Python拡張2026.10.0／Jupyter拡張2025.9.1、showCellStatusBarはvisible。
- 画面で2番目と3番目のセルの言語選択の左隣にZizaiを確認。1番目の初期化セルにはない。
- selectedイベントと最終snapshotで2番目はfake、3番目はpython。セルごとの選択変更と同時保持を確認。全セルexecutionOrderはnull、outputTypesは空で、Python実行前の選択を確認できる。Escキャンセルはクラウド検査のみで、実機の実施報告はない。
- 画面のカーネル選択欄はPython 3.14.3。選択欄の表示であり、カーネルを実行してPython版を取得した結果ではない。以前の3.12.13想定と区別する。
- 利用者は別ウィンドウが開き操作できたが、背後のログでは起動付近にDisposableStoreの同じ4件のstackが再発したと報告。新版はOutputChannelを作らないため、その直接の作成呼出しを新試作へ帰属できない。他拡張／VS Code内部の呼出元特定が必要。起動成功をエラー解消とは扱わない。
- DEP0169に加えてDEP0040を受領。Copilot Chatの19MBファイルに対するLARGE fileログもあるが、OutputChannelエラーの呼出元を示すstackではなく、Copilotを原因と断定できない。Kernel: startingも実行結果の証拠にはしない。混在ログ内の全行が同一プロセスで出たかも未確認。

## 終了時の文字化けログ

利用者の追加報告は `�G���[: �v���Z�X "14012" ��������܂���ł����B`。`エラー: プロセス "14012" が見つかりませんでした。` をCP932で符号化し、UTF-8としてreplacement付き復号すると投稿文と一致した。Windowsの日本語出力を誤った文字コードで読んだ場合に再現するため、試作のセル文字列やNotebookデータの破損とは扱わない。

意味は対象PIDが見つからないというもの。デバッガ／ランチャー等が終了済みプロセスを停止しようとした可能性があるが、発行コマンドと終了時系列の詳細は未取得で、taskkill等の特定コマンドやDisposableStoreとの因果関係は断定しない。起動成功とUI操作の実機証跡をこの終了ログで取り消す理由はない。グローバルの文字コードやVS Code本体は変更しない。

再現コマンド（クラウドNode検査とは別のPython補助）：

```sh
python -c 'print("エラー: プロセス \"14012\" が見つかりませんでした。".encode("cp932").decode("utf-8", errors="replace"))'
```

## クラウドでの実施条件

開始時HEADは `d3e8117bb438f49342daa679136f7d25b7942713`、ブランチは `spike/task-001-01-notebook-ui`。Node 24.19.0で [検査コマンド](../../../tests/manual/TASK-001-01-statusbar.md#クラウド検査) を実行し、4モード生成・check.mjs・共有4件・新版5件は合格。JS 12ファイルの `node --check`、起動／タスク／manifest／workspaceのJSON解析、変更文書の相対リンクと `git diff --check` も合格。これは画面の合格や前回エラーの実機再現ではない。製品の共通テストランナーは未実装のため、試作の全テストファイルを直接実行した。

## 確認結果と後続への影響

| 項目 | 結果 | 根拠 |
| --- | --- | --- |
| 標準APIでセル下部へ寄与可能か | 合格（API調査） | 上記定義とVS Code実装。画面の合格ではない |
| 初期化除外・対象セルへの選択・キャンセル・閉じたセルの拒否・終了後の選択結果破棄 | 合格（クラウド） | statusbar.test.cjs 5件。最初の未実装状態ではprovider未登録で5件失敗、実装後5件合格 |
| 共有状態のセル間／Notebook間の独立 | 合格（クラウド） | 既存toolbar-state.test.cjs 4件 |
| 実行前から言語選択の隣に表示 | 合格（実機） | 新版の画面とexecutionOrder:null、空出力のsnapshot |
| 実機で選択・ラベル更新・初期化非表示 | 合格（確認範囲） | S1／S2の選択変更／S3を画面・操作報告・イベントと照合。S2のEscは実機未実施 |
| 前回の警告の起点特定と解消確認 | 未解決（実機で再発） | 新版でもDisposableStoreの4件が再発。診断起動との比較は未実施 |
| 標準実行・出力消去・タブ切替等の追加検証 | 未実施（後回し） | 利用者の指示を維持 |
| Kiro | 対象外 | 利用者の指示を維持 |

結論：**希望位置での選択UIの基本動作は実機確認済み**。起動時エラーは再発しており原因の起点特定は継続中。HTMLフォームの常設、処理の正式実装、セルsource生成、詳細フォームの配置を確定しない。旧版での調査完了記録は履歴として保持し、TASK-001-01は起動エラーの切り分け待ちで進行中を維持する。
