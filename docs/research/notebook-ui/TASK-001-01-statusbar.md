# TASK-001-01 言語選択の隣の選択UI（試作）

更新日：2026-10-20。**試作・自動検査・手順を準備済み。セル下部の実機表示は未実施。**

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
| disposed DisposableStoreへの追加 | 受領stackの `doCreateOutputChannel` と対象版ソースが対応。OutputChannelは内部でディレクトリ作成・登録をawaitし、その後storeへlogger等をaddする。作成完了前にOutputChannelをdisposeすると、破棄済みstoreへaddする競合が起き得る | 対象拡張名・channel名・dispose時点は受領stackにない。前試作もOutputChannelを作るが、他拡張も使う。利用者の実機で競合した起点は未特定、同実機での再現・解消は未確認 |

根拠：[extHostOutput.ts](https://github.com/microsoft/vscode/blob/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/src/vs/workbench/api/common/extHostOutput.ts) のcreateOutputChannel／doCreateOutputChannel／createExtHostOutputChannelと、[lifecycle.ts](https://github.com/microsoft/vscode/blob/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/src/vs/base/common/lifecycle.ts) のDisposableStore.add。後者はこの文を `console.warn(Error.stack)` で出す。ログのErrorという表示だけで拡張適用失敗やNotebook非表示の原因とは確定できない。実際に利用者はその後Notebookを開けている。

今回の試作ではOutputChannel作成経路を使用しない。さらに終了後の非同期選択結果を破棄する。これは試作の依存と終了時動作の整理であり、VS Code内部の競合そのものを修正した意味ではない。別プロセス／他拡張の警告が消える保証もしない。診断起動設定と比較手順は [手動手順](../../../tests/manual/TASK-001-01-statusbar.md#エラーが再発した場合だけ行う診断) に記載。

## クラウドでの実施条件

開始時HEADは `d3e8117bb438f49342daa679136f7d25b7942713`、ブランチは `spike/task-001-01-notebook-ui`。Node 24.19.0で [検査コマンド](../../../tests/manual/TASK-001-01-statusbar.md#クラウド検査) を実行し、4モード生成・check.mjs・共有4件・新版5件は合格。JS 12ファイルの `node --check`、起動／タスク／manifest／workspaceのJSON解析、変更文書の相対リンクと `git diff --check` も合格。これは画面の合格や前回エラーの実機再現ではない。製品の共通テストランナーは未実装のため、試作の全テストファイルを直接実行した。

## 確認結果と後続への影響

| 項目 | 結果 | 根拠 |
| --- | --- | --- |
| 標準APIでセル下部へ寄与可能か | 合格（API調査） | 上記定義とVS Code実装。画面の合格ではない |
| 初期化除外・対象セルへの選択・キャンセル・閉じたセルの拒否・終了後の選択結果破棄 | 合格（クラウド） | statusbar.test.cjs 5件。最初の未実装状態ではprovider未登録で5件失敗、実装後5件合格 |
| 共有状態のセル間／Notebook間の独立 | 合格（クラウド） | 既存toolbar-state.test.cjs 4件 |
| 実行前から言語選択の隣に表示 | 未実施（実機） | 新版の画面なし。旧右上ツールバーの結果を流用しない |
| 実機で選択・ラベル更新・初期化非表示 | 未実施（実機） | [S1〜S3](../../../tests/manual/TASK-001-01-statusbar.md) を準備 |
| 前回の警告の起点特定と解消確認 | 未実施（実機） | 発生経路は上記調査済み。診断比較が必要 |
| 標準実行・出力消去・タブ切替等の追加検証 | 未実施（後回し） | 利用者の指示を維持 |
| Kiro | 対象外 | 利用者の指示を維持 |

結論：セル下部への公開APIは存在し、最小試作と確認準備は完了。**希望位置でのUI成立は実機待ち**。HTMLフォームの常設、処理の正式実装、セルsource生成、詳細フォームの配置を確定しない。旧版での調査完了記録は履歴として保持し、TASK-001-01の現在状態は進行中へ戻す。
