# TASK-001-01 セルツールバーの最小実証

更新日：2026-10-20。**VS Code 1.142.0／Windowsでセルツールバーの基本動作を実機確認。セルツールバー選択UIの調査・機能確認は完了。標準機能との追加確認は利用者指示で後回し（未実施）。**

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
| 未実行セルでのボタン・メニュー表示（T1） | **合格（実機）** | 利用者提供の画面・選択操作の報告と、実行前のselectedイベントを照合 |
| 初期化セルだけの非表示（T2） | **合格（実機）** | 利用者が「でないです」と確認。snapshotでもinitのselected=null、実行番号なし |
| 押したセルの選択処理（T3） | **合格（実機、確認できた操作）** | セル2／3それぞれの選択通知を利用者が確認。ログにもindex=1／2のpython・fake選択あり。source・metadataの厳密な前後diffは未取得 |
| source・標準outputとの共存、通常実行後の維持（T4） | **合格（実機、利用者報告＋ログ）** | 利用者が標準実行について「はい。問題ないです」と報告。snapshotでindex=1／2に標準stdout・text/plainと実行順2／4、selected=fakeを確認。ログは出力の実値や編集差分を含まない |
| 例外・明示的な出力消去後の維持（T5） | **未実施** | 例外の発生や手動の出力消去を確認できる証跡はない |
| 別タブ復帰・スクロール・折りたたみ（T6） | **未実施** | 操作・結果の報告なし |
| Kiroでの確認 | **対象外（今回）** | 利用者の「一旦、kiroは無視でok」に基づく。過去の未実施結果は変更しない |

コードレビューでは標準submenuから対象セル引数が渡るソース経路も照合し、重大・重要な指摘はなかった。クラウド検査もレビューも、VS Code画面を起動した確認の代わりにはならない。

## 利用者による実機確認の証跡

2026-10-20、利用者がデスクトップを操作し、本会話へ画面・操作結果・Outputログを返却した。記録期間は**15:05〜15:15 JST**（ログ内はUTC）、snapshotは15:15:27.584 JST。今回の実機結果は利用者による確認であり、クラウドで画面を操作した結果ではない。

- [受領したOutputログ](evidence/2026-10-20-toolbar.jsonl)：76行。activated=1、toolbar-context-ready=20、selected=16、cell-changed=38、snapshot=1。改行をCRLFからLFへ正規化し、JSONの内容は保持した。元の添付ファイルのSHA-256は `ef11cabe8e69bfc413acac6ea9e861065648e2a84022f6c56e6bd34051a98f48`。
- 案内した取得元は `94da3cba44e09a4396aaa985c9539df6696408e6` のZIP、試作コード版は上記 `c2486174b5445d7c1f73de51dc1c47b3522c984d`。端末のgit HEAD・未コミット差分は未取得。ログでは試作0.0.2を確認した。
- 提供された画面で、未実行Notebookの2番目のセル右上にセルツールバーを確認。その後のメニュー選択・対象セル通知・初期化非表示は会話中の利用者報告と照合した。

| 環境項目 | 実測・確認内容 |
| --- | --- |
| IDE | Visual Studio Code 1.142.0。ビルドcommitは未取得 |
| OS | Windows（platform=win32）。OS詳細版・CPUは未取得 |
| Extension Host Node | v24.21.0 |
| 試作 | toolbarモード、0.0.2 |
| Python拡張 | 2026.10.0 |
| Jupyter拡張 | 2025.9.1 |
| カーネルPython／ipykernel | 実版は未取得。Python3.12.13は事前想定であり、実測値として扱わない |

最終snapshotでは、初期化セルindex=0はselected=null・outputなし・未実行。通常Pythonセルindex=1と処理セルindex=2はselected=fakeのまま、標準MIMEのoutputと実行順を保持している。index=2は実行後にもselectedイベントがあり、再操作できたことをログで確認できる。さらに通常Pythonセルindex=3の追加・選択も記録されているが、セル追加等を含むT6全体の合格へは拡張しない。

ログ内のoutputs=0から2への変化だけで、T5の「手動で出力を消去する」を実施したとは判断しない。出力の実値 `6` やPython実行成功フラグは本ログにはなく、標準実行についての利用者報告と、記録された出力形式・実行順を分けて扱う。

起動時には `DEP0169` と `DisposableStore ... already been disposed of` のログも会話で受領した。別ウィンドウは開いたままで、その後コマンドからNotebookを開いて上記操作を実施できた。警告・エラーの発生原因や再現条件は未特定で、修正・解消済みとは記録しない。

## 現時点の結論

**標準APIによるセルツールバー方式の基本動作は、VS Code 1.142.0／Windowsで成立を確認した。** メニュー表示・対象セルの選択・初期化セルの非表示・標準実行と出力の共存・通常実行後の選択保持を、画面と利用者報告・ログで確認できた。HTMLフォームの常設や製品全体の完成を示す結果ではない。

2026-10-20の追加指示により、今回の判定対象はZizaiのセルツールバー選択UIの機能自体とし、標準Notebook機能との追加確認は後回しとする。受領済みの画面・操作報告・ログを再利用し、同じ操作やログの再送は要求しない。T5／T6は未実施のまま後続検証へ引き継ぎ、今回の調査完了の必須条件から外す。環境表の未取得情報も残し、標準実行の結合検証時に補う。

**TASK-001-01は調査として完了**とする。結論は「VS Codeのセルツールバーによる選択UIは成立、HTMLフォーム常設は標準APIの調査上不適合で実機成立は未確認」。HTMLフォームを含むUI全体、本体実装、標準機能との全結合検証が完了したという意味ではない。

初期化の識別は試作専用、選択値の永続保存や正式なコネクタ処理は未実装。HTMLフォームの先行調査は [別記録](TASK-001-01.md) に残し、今回のツールバー表示と合否を混同しない。

## 確認範囲の補足

ログにはセルごとにpython／fakeを選択したイベントがあり、最終snapshotでは複数セルがfakeとなっている。対象セルごとのコマンド受信と、通常実行後の選択保持を確認できる。一方、異なる選択値を同時に保持した実機snapshotを取得したとは記録しない。セル間・Notebook間の状態独立は既存の単体検査でも確認済みであり、受領済みログの再送を完了条件にはしない。
