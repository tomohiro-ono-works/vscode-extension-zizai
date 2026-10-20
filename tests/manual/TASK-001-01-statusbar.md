# TASK-001-01 言語選択の隣：実機確認手順

対象：Windows／VS Code 1.142.0（または利用中の最新版を記録）、試作0.0.3。前回の拡張はPython 2026.10.0／Jupyter 2025.9.1。今回はカーネル選択・Python実行は不要。Kiroと標準機能の追加テストは対象外。

## 起動

1. 最新の `spike/task-001-01-notebook-ui` を取得し、リポジトリ直下をVS Codeで開く。前回のExtension Development Hostは閉じる。同じ拡張IDを使うため旧版と同時起動しない。
2. 「実行とデバッグ」で **TASK-001-01: Beside Cell Language (PROTOTYPE)** を選び、F5。Node.jsがPATHに必要で、npm installは不要。preLaunchTaskが `node tests/notebook-ui-gate/prepare.mjs statusbar` を実行する。
3. 別ウィンドウに試作用workspaceと `empty.ipynb` が開く。Notebookが開かなければ、その別ウィンドウでCtrl+Shift+P → **Zizai Probe: Open Empty Notebook**。Jupyter拡張が有効で、workspaceが信頼されていることを確認する。

試作用workspaceの `notebook.showCellStatusBar` は `visible`。設定が別のスコープで上書きされている場合は、別ウィンドウの設定で値を確認する。利用者のグローバル設定を変更する必要はない。

## 今回の操作（Pythonは実行しない）

| ID | 操作 | 期待結果 |
| --- | --- | --- |
| S1 | 2番目のセルを見る | 右下の言語選択「Python」の左隣付近に **Zizai: 通常Python ▾**。上部ツールバーではない。位置・間に別項目があるかも確認 |
| S2 | そのZizai表示をクリック → **架空コネクタ（試作）** を選ぶ | VS Code標準の選択一覧が画面上部に開く。選択後、そのセルのラベルだけが **Zizai: 架空コネクタ ▾** に変わる。続けて3番目を通常Pythonへ変更し、2番目の表示が変わらないことを確認。もう一度開いてEscなら選択を維持 |
| S3 | 1番目の初期化セルを見る | 言語選択「Python」はあるがZizai表示はない |

ボタン直下に一覧を展開する形は今回の標準API試作では提供しない。source・metadata・output・セル言語は変更せず、選択だけではPythonを実行しない。状態はメモリのみで、Notebookを閉じると破棄される。

返してほしい情報は **S1〜S3の結果と、言語選択の隣が分かる画面1枚**。従来ログの再送は不要。異常がある場合だけ、別ウィンドウのCtrl+Shift+P → **Zizai Probe: Report Cell Status Bar** で開くJSONの内容を返す。版・選択・設定値を含むが、sourceや実データは記録しない。

## 現在の実施結果

2026-10-20、S1・S2の選択変更とセル別保持・S3は画面／報告／JSONログで確認済み。同じUI操作やログの再送は不要。S2のEscキャンセルは実機未実施。起動エラーは新版でも再発したため、次は以下の診断起動との比較だけを行う。

## エラーが再発した場合だけ行う診断

前回のエラーは [調査記録](../../docs/research/notebook-ui/TASK-001-01-statusbar.md#起動時のエラー調査) に分けて記載。原因の起点は未特定なので、新版で消えたかも記録する。

1. 通常の起動で、警告が出た時点（F5直後／Notebookを開く時／閉じる時）と、別ウィンドウが残ったかを記録。正常な標準機能を一通りテストする必要はない。
2. 通常の別ウィンドウを閉じ、**TASK-001-01: Startup Diagnostics (installed extensions disabled)** でF5。これは `--disable-extensions` でインストール済み拡張を外し、開発対象の試作を比較する設定。Jupyterも無効なのでNotebook表示テストはしない。別ウィンドウでCtrl+Shift+P → **Zizai Probe: Report Cell Status Bar** を実行し、開発対象を明示的に起動する（Notebookを開かないと自動起動されないため）。JSONにactivatedとprobeVersion:0.0.3があることを確認する。その後、起動直後・コマンド実行時・終了時の警告有無だけを比較する。
3. 診断用は `--log=trace` と `NODE_OPTIONS=--trace-deprecation` を指定する。後者が対象プロセスへ引き継がれればDEP0169の呼出元stackが出る。起動元CLI等、別プロセスの警告には効かない場合がある。stackが出なければ特定完了とはしない。
4. 再発した側の「デバッグコンソール」と、別ウィンドウの「表示 → 出力 → Log (Extension Host)」で該当時刻の前後を保存する。名称は表示言語によって異なる。必要なら **Developer: Open Logs Folder** で該当セッションのexthostログを探す。個人パス等は伏せる。

返してほしい情報：通常／診断起動のどちらで再発したか、発生時点、エラー前後とDEP0169の呼出元stack（出た場合）。診断側だけで消えても、他拡張・Jupyter起動条件等の差があるため特定の拡張を犯人と断定しない。新版でも同じエラーなら、新版はOutputChannelを作らないことと照合して次の切り分けを行う。

## クラウド検査

```sh
node tests/notebook-ui-gate/prepare.mjs stable
node tests/notebook-ui-gate/prepare.mjs insets
node tests/notebook-ui-gate/prepare.mjs toolbar
node tests/notebook-ui-gate/prepare.mjs statusbar
node tests/notebook-ui-gate/check.mjs
node tests/notebook-ui-gate/toolbar-state.test.cjs
node tests/notebook-ui-gate/statusbar.test.cjs
```

上記では画面位置・選択一覧の描画・Windows起動時エラーの再現は確認できない。
