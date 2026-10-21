# TASK-001-02 フォーム表示場所の候補比較

調査日：2026-10-21。対象：VS Code 1.142.0、commit `d956e8a6ac5d904486557eea07e1d6bd62a4d36f`。**APIの再照合と候補整理まで実施。配置方針の決定・製品実装・追加の実機検証は行っていない。** Kiroは今回の対象外。

## 要件と今回確認した境界

[全体設計](../../designs/01全体設計.md) 第12節と [Notebook UI設計](../../designs/02NotebookUI設計.md) にある条件は、通常のJupyterコードセル内にPython実行前からフォームを常設し、標準のPythonコード欄・出力と共存すること。セル実行後の表示維持も必要になる。

[TASK-001-01](TASK-001-01-statusbar.md) で実機確認した言語選択隣のボタンは、標準のCell Status BarとQuickPick。これはコネクタ等の選択に使える。NodeFormが必要とするHTML入力領域は追加しないため、フォームの表示場所は別に検討する。

今回、固定版の標準API型定義、editorInsetsの提案型定義、Extension Host／Main ThreadのInsets実装、提案APIの許可処理を再取得して照合した。参照箇所は末尾の一次資料に示す。クラウドでのソース照合を画面表示の合格へ読み替えない。

## 候補比較

| 候補 | API区分・表示位置 | Python実行前のフォーム | 通常のセル内常設という条件 | 制約・後続への影響 |
| --- | --- | --- | --- | --- |
| Cell Status Bar／セルツールバー → QuickPick | 標準。セルの文字・ボタンから選択メニューを開く | 選択操作は実行前に可能。任意のHTMLフォームは埋め込めない | 詳細フォーム用には不適合 | 希望位置での選択は確認済み。フォームの配置を解決したとは扱わない。QuickPickへ変更しても複数項目の常設フォームにはならない |
| editorInsets | 試験的。TextEditorの行間へWebviewを置く | API上はPythonやoutputを前提としない。Notebookセルへの適用は実機未確認 | **未判定**。現要件を保って調べる候補 | 可視TextEditorが必要。NotebookCellから直接挿入するAPIではない。非表示での破棄、高さ、スクロール・仮想化、フォーカス、実行後の維持を要確認。提案APIの許可と配布条件の確認が必要 |
| WebviewPanel | 標準。独立したエディタータブ。Notebookの横にも配置できる | 部品をHTMLで表示するAPIはある。評価用0.0.1を準備済み、実機未実施 | セル内ではないため現条件に不適合 | 候補として選ぶ場合はフォームの場所に関する仕様判断が必要。対象セルの明示・切替、複数Notebook、下書きの帰属を後続で設計する。評価用タブの存在を製品への採用と扱わない |
| WebviewView | 標準。サイドバー等のView | 部品をHTMLで表示するAPIはある。今回の試作・実機は未実施 | セル内ではないため現条件に不適合 | フォーム配置に関する仕様判断が必要。セル選択と表示対象の対応や、選択変更中の下書きの扱いを決める必要がある |
| Notebook Renderer | 標準。セルoutputのMIMEをHTMLで描画 | 保存済みoutputなら表示できるが、outputのないセルには表示領域を作らない | 現条件に不適合 | 実行・出力消去でフォームが失われ得る。出力の挿入・再注入を常設の根拠にしない。標準出力と同じ領域を使うため、今回の代替案として採用しない |
| Custom Editor／IDE側の機能追加 | Custom Editorは標準API。IDE改修は通常の拡張APIの範囲外 | HTMLを扱う設計は考えられるが今回未評価 | 通常Notebookを保った拡張としての成立根拠はない | 独自editorは標準Notebookを置き換える。IDE改修はVS Code側の変更・更新追従が必要。いずれも今回の作業対象外で、実装しない |

## セル内案に残る確認

editorInsetsの型は `createWebviewTextEditorInset(editor: TextEditor, line, height, options)`。返される高さはreadonlyで、フォームの条件表示に追従する高さ変更APIは当該提案型に見当たらない。表示内容が増える場合の切れ・スクロール・再生成の扱いを実機で確認する必要がある。

Extension Host実装は可視TextEditorから外れたinsetを破棄する。Main Thread実装はeditorのIDとURIを照合し、一致しない場合は破棄通知を返す。セルが画面外へ出る、折りたたむ、Notebook内部のeditorが作り直される、といった場面での表示と値の復元は、APIが存在するだけでは保証されない。単に再描画できたことと表示が維持できたことも区別する。

既存の [Insets試作と実機手順](../../../tests/manual/TASK-001-01.md) はこの候補の確認材料。今回それを実行済みにはしない。Stable版の開発ウィンドウでも提案APIが自動許可されるとは限らず、`enabledApiProposals` とID限定の `--enable-proposed-api` 等の条件を要する。通常配布への採用可否は別の判断になる。

## 後続へ渡す判断材料

- セル内常設の条件を維持する場合：editorInsets候補の実機評価と提案API依存の受け入れ判断が残る。これが成立する前にセル内フォームの製品実装へ進まない。
- 標準APIを使って詳細フォームを別画面へ置く場合：WebviewPanel／WebviewViewが比較候補。フォームの場所の仕様変更を判断してから、対象セルとの対応や下書き・確定の詳細を設計する。今回この変更を決定しない。
- 現在のWebview部品評価が合格した場合でも、分かるのはNodeFormの読込・テーマ・イベント・OS選択の適合性。セル内常設の実現可否は未判定のまま残る。

TASK-001-02は部品評価の実機待ちを維持する。TASK-001-03以降、正式なUI／Host契約、本体実装は開始していない。調査資料として候補と判断が必要な箇所を明示し、現行仕様は変更しない。

## 一次資料

すべて上記の固定commitを2026-10-21に再照合した。先行調査は [TASK-001-01のAPI調査](TASK-001-01.md#apiの調査結果) を参照。

- [標準API型定義](https://github.com/microsoft/vscode/blob/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/src/vscode-dts/vscode.d.ts)：NotebookEditor（15337行）、NotebookCellOutput（15854行）、NotebookCellStatusBarItem（16286行）、showQuickPick（11421行以降）、WebviewPanel生成（11547行）、WebviewView（10225行）とProvider登録（11752行）、CustomTextEditorProvider（10358行）。
- [editorInsetsの提案型定義](https://github.com/microsoft/vscode/blob/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/src/vscode-dts/vscode.proposed.editorInsets.d.ts)：TextEditor引数とreadonlyのheight。
- [Extension HostのInsets実装](https://github.com/microsoft/vscode/blob/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/src/vs/workbench/api/common/extHostCodeInsets.ts)：可視editorの確認、不可視化時の破棄、Main Threadへ渡すeditorとURI。
- [Main ThreadのInsets実装](https://github.com/microsoft/vscode/blob/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/src/vs/workbench/api/browser/mainThreadCodeInsets.ts)：CodeEditorのID／URI照合、行間のWebview、model変更・editor破棄時の処理。
- [提案APIの許可処理](https://github.com/microsoft/vscode/blob/d956e8a6ac5d904486557eea07e1d6bd62a4d36f/src/vs/workbench/services/extensions/common/extensionsProposedApi.ts)：Stableと開発モードの扱い、起動フラグ・product設定の許可。
