# TASK-001-01 セルツールバーの最小実証

更新日：2026-10-20。**標準APIの調査と試作・クラウド検査まで実施。VS Codeの画面確認は未実施。**

- [呼称と選択UIの合意](../../decisions/2026-10-19-notebook-ui-terms.md)
- [試作](../../../tests/notebook-ui-gate/README.md)／[今回の操作手順](../../../tests/manual/TASK-001-01-toolbar.md)
- [Task](../../tasks/active/TASK-001/TASK-001.md#task-001-01)

## 今回の範囲

利用者が合意した「セルツールバーへボタンを追加し、選択メニューを開く」方式の最小試作を進める。利用者の追加指示により、**今回はVS Codeのみを対象とし、Kiroは対象外**。製品全体のKiro対応を取り消す判断ではなく、過去の未実施結果を合格へ変更するものでもない。

作業ブランチは `spike/task-001-01-notebook-ui`、開始時commitは `a0313f0`、試作コードの確定版は `c2486174b5445d7c1f73de51dc1c47b3522c984d`。正本は `tests/notebook-ui-gate/toolbar*.cjs` と `toolbar.package.json`、prepareによる生成物はGit無視対象の `dist/toolbar/`。同フォルダーのHTMLフォーム用先行実験は保持し、今回の生成物・API依存と分離する。本体の `apps/`、コネクタ、正式な契約やセル識別方式、Python実行処理は実装しない。

## 標準APIで確認できたこと

調査対象：VS Code 1.142.0、commit `d956e8a6ac5d904486557eea07e1d6bd62a4d36f`。

| 対象 | 調査で確認した内容 | 根拠 |
| --- | --- | --- |
| メニューボタンの追加 | `contributes.submenus` と `contributes.menus` の `notebook/cell/title` は標準の拡張ポイント。submenuを禁止する指定がなく、標準ToolBarがdropdownを描画する | [menusExtensionPoint](https://github.com/microsoft/vscode/blob/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/src/vs/workbench/services/actions/common/menusExtensionPoint.ts)、[cellToolbars](https://github.com/microsoft/vscode/blob/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/src/vs/workbench/contrib/notebook/browser/view/cellParts/cellToolbars.ts) |
| ボタンの位置 | `group: inline@5` を使い、セルツールバーのprimary actionへ寄与する。表示タイミング・位置・アイコン・overflowはVS Codeの設定／標準動作に従う | 上記cellToolbarsの `getCellToolbarActions` |
| 初期化セルの非表示 | `notebookCellResource` にセルURI文字列が設定される。標準の `setContext` で対象URI一覧を登録し、`notebookCellResource in zizaiProbe.toolbarCells` のwhen条件で制限する | [notebookContextKeys](https://github.com/microsoft/vscode/blob/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/src/vs/workbench/contrib/notebook/common/notebookContextKeys.ts)、[cellContextKeys](https://github.com/microsoft/vscode/blob/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/src/vs/workbench/contrib/notebook/browser/view/cellParts/cellContextKeys.ts) |
| 操作対象セル | ツールバーが渡すcell contextはExtension HostでNotebookCellへ変換される。試作はこの引数だけを使い、active cellへフォールバックしない | 上記cellToolbars、[extHostNotebook](https://github.com/microsoft/vscode/blob/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/src/vs/workbench/api/common/extHostNotebook.ts) のargument processor |

この経路はHTMLフォームの配置口や `editorInsets` を必要としない。`notebookCellResource` 等の具体的なcontext keyは上記版の実装で照合したもので、全VS Code版で同じ挙動を検証した意味ではない。実機版が異なる場合は版とエラーを記録する。

## 試作の動作

- モード `toolbar`、試作版0.0.2、拡張ID `zizai-lab.task-001-01-probe`。最低VS Code宣言は `^1.105.0`、対象実機は利用者の最新Stable。依存npmパッケージなし。
- `empty.ipynb` の通常Pythonセルと処理セルに「Zizai（試作）」メニューを寄与する。候補は「通常Python（試作）」「架空コネクタ（試作）」のみ。fixture専用metadataで初期化セルを除外し、通常セルには識別metadataを要求しない。
- 選択はExtension Hostの一時メモリに保持。通知とReportのログで、実際にクリックしたセルの選択を確認できる。source・metadata・outputを変更せず、Pythonも実行しない。Notebookを閉じたら選択を破棄する。
- 配布物にHTMLフォーム、Renderer、Webview、提案API宣言は含まれない。VS Code／Jupyter自体のファイルも変更しない。正式な保存・生成・実行やフォーム部品採用は扱わない。

## クラウド検査と結果

Node.js 24.19.0で実施。`node --test` の分離プロセス実行ではファイル単位の汎用失敗になったため、同じ `node:test` のケースを `node <testfile>` で直接実行して結果を取得した。最初の未実装状態は4件中3件が期待どおり失敗し、実装後は4件とも合格。

```sh
node tests/notebook-ui-gate/toolbar-state.test.cjs
node tests/notebook-ui-gate/prepare.mjs stable
node tests/notebook-ui-gate/prepare.mjs insets
node tests/notebook-ui-gate/prepare.mjs toolbar
node tests/notebook-ui-gate/check.mjs
```

| 確認項目 | 結果 | 範囲・根拠 |
| --- | --- | --- |
| 対象セル・初期化除外のロジック | 合格（クラウド） | 空のfixtureを対象に通常Python／処理だけを抽出する検査 |
| 対象セルへの選択・保持・破棄 | 合格（クラウド） | 別セル／別Notebookの選択独立、refresh後保持、close相当の除去、無効・古い引数や未知選択の拒否 |
| 生成物・設定 | 合格（クラウド） | 3モードのmanifestとfixture整合。toolbarにHTML／Renderer／提案APIを含めない構成を検査 |
| 未実行セルでのボタン・メニュー表示 | **未実施** | VS CodeのT1待ち |
| 初期化セルだけの非表示 | **未実施** | 実際のwhen評価・標準ツールバー表示はT2待ち |
| 押したセルの選択処理 | **未実施** | UIから渡る引数・通知と状態の照合はT3待ち |
| source・標準outputとの共存、実行・例外・出力消去後の維持 | **未実施** | T4〜T6待ち |
| Kiroでの確認 | **対象外（今回）** | 利用者の「一旦、kiroは無視でok」に基づく。過去の未実施結果は変更しない |

コードレビューでは標準submenuから対象セル引数が渡るソース経路も照合し、重大・重要な指摘はなかった。クラウド検査もレビューも、VS Code画面を起動した確認の代わりにはならない。

## 現時点の結論

**セルツールバー方式は、標準の拡張ポイントによる試作を準備できた。VS Code上での成立は実機確認待ち。** TASK-001-01は完了にせず、T1〜T6の結果・正確なIDE／拡張／カーネル版・画面・Outputログの返却を待つ。

初期化の識別は試作専用、選択値の永続保存や正式なコネクタ処理は未実装。HTMLフォームの先行調査は [別記録](TASK-001-01.md) に残し、今回のツールバー表示と合否を混同しない。
