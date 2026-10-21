# TASK-001-01 検証専用試作

本番コードではない。`apps/` へ取り込まず、正式なmetadata・通信契約・コネクタを定義しない。

**現在の対象（2026-10-20）はセル右下の言語選択の隣。** [今回の手順](../manual/TASK-001-01-statusbar.md) を使い、F5で **TASK-001-01: Beside Cell Language (PROTOTYPE)** を起動する。Kiroは今回の対象外。新版の希望位置への表示・選択・初期化非表示は実機確認済み。起動時のOutputChannel関連エラーは再発しており、[TASK-007](../../docs/tasks/active/TASK-007/TASK-007.md)へ未解決のまま移管。TASK-001-01は選択UIの調査として完了。

`statusbar` は標準セルステータスバー＋QuickPickの試作0.0.3。表示ボタンはセル下部、選択一覧は画面上部に開く。セルの直下へ展開するメニューではない。選択はHostメモリのみで、source・metadata・output・言語を変更せずPythonも実行しない。OutputChannelを作らず、診断はconsoleとJSONレポートを使う。

- [API調査・起動エラーの調査・現在の判定](../../docs/research/notebook-ui/TASK-001-01-statusbar.md)
- [対象版・起動・確認操作](../manual/TASK-001-01-statusbar.md)
- [Task](../../docs/tasks/active/TASK-001/TASK-001.md#task-001-01)

旧 `toolbar` 0.0.2は右上ツールバーの比較履歴として保持する。[旧結果](../../docs/research/notebook-ui/TASK-001-01-toolbar.md) は新版の合格根拠にはしない。

先行調査の `stable` は標準Status Barと出力Rendererの対照実験、`insets` は試験的 `editorInsets` の実験。拡張IDは全モードとも `zizai-lab.task-001-01-probe` なので同時起動しない。

依存パッケージ・ビルドツールは不要。ソースの `package.json`、`toolbar.package.json`、`statusbar.package.json` は生成元であり、直接ロードしない。準備スクリプトが共有ソースを無視対象の `dist/<mode>/` へコピーし、実験モードだけに `enabledApiProposals` を付ける。

```sh
node tests/notebook-ui-gate/prepare.mjs stable
node tests/notebook-ui-gate/prepare.mjs insets
node tests/notebook-ui-gate/prepare.mjs toolbar
node tests/notebook-ui-gate/prepare.mjs statusbar
node tests/notebook-ui-gate/check.mjs
node tests/notebook-ui-gate/toolbar-state.test.cjs
node tests/notebook-ui-gate/statusbar.test.cjs
```

上記は構成・fixtureの検査にすぎず、VS Codeを起動せず、UIの合格を示さない。F5の設定はリポジトリ直下の `.vscode/launch.json` にある。

試作はfixtureの識別用metadata `task00101Probe.role` を読むだけで、source・metadata・outputを書き換えない。未識別の通常Pythonセルも、識別済みfixtureと同じNotebook内で対象になる。初期化セルはUIを生成しない。値はExtension Hostの一時メモリだけに保持し、Notebookを閉じると破棄する。保存・Undo・正式なセル識別・フォーム部品再利用は今回の検証対象外。
