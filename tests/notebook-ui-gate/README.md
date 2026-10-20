# TASK-001-01 検証専用試作

本番コードではない。`apps/` へ取り込まず、正式なmetadata・通信契約・コネクタを定義しない。

**現在の対象（2026-10-20）はVS Codeのセルツールバー。** [今回の手順](../manual/TASK-001-01-toolbar.md) を使い、F5で **TASK-001-01: Cell Toolbar (PROTOTYPE)** を起動する。Kiroは今回の対象外。

`toolbar` は標準APIのボタン＋選択メニューだけを含む試作0.0.2。選択はHostの一時メモリだけに保持し、セルsource・metadata・outputを変更せず、Pythonも実行しない。HTMLフォーム・Renderer・試験的APIは生成物に含まれない。

- [API調査・現在の判定](../../docs/research/notebook-ui/TASK-001-01-toolbar.md)
- [対象版・デスクトップ手順・返却項目](../manual/TASK-001-01-toolbar.md)
- [Task](../../docs/tasks/active/TASK-001/TASK-001.md#task-001-01)

先行調査の `stable` は標準Status Barと出力Rendererの対照実験、`insets` は試験的 `editorInsets` の実験。拡張IDは全モードとも `zizai-lab.task-001-01-probe` なので同時起動しない。

依存パッケージ・ビルドツールは不要。ソースの `package.json` と `toolbar.package.json` は生成元であり、直接ロードしない。準備スクリプトが共有ソースを無視対象の `dist/<mode>/` へコピーし、実験モードだけに `enabledApiProposals` を付ける。

```sh
node tests/notebook-ui-gate/prepare.mjs stable
node tests/notebook-ui-gate/prepare.mjs insets
node tests/notebook-ui-gate/prepare.mjs toolbar
node tests/notebook-ui-gate/check.mjs
node tests/notebook-ui-gate/toolbar-state.test.cjs
```

上記は構成・fixtureの検査にすぎず、VS Codeを起動せず、UIの合格を示さない。F5の設定はリポジトリ直下の `.vscode/launch.json` にある。

試作はfixtureの識別用metadata `task00101Probe.role` を読むだけで、source・metadata・outputを書き換えない。未識別の通常Pythonセルも、識別済みfixtureと同じNotebook内で対象になる。初期化セルはUIを生成しない。値はExtension Hostの一時メモリだけに保持し、Notebookを閉じると破棄する。保存・Undo・正式なセル識別・フォーム部品再利用は今回の検証対象外。
