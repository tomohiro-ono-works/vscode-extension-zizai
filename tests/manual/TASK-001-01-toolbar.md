# TASK-001-01 セルツールバーの手動確認

定義版：2026-10-20。今回の対象は**VS Codeだけ**。Kiroは利用者の指示により今回の対象外とし、以前の未実施結果はそのまま残す。HTMLフォームの手順は [先行実験](TASK-001-01.md) として保存する。

## 対象と起動

- 対象ブランチ：`spike/task-001-01-notebook-ui`。起動前に `git rev-parse HEAD` と `git status --short` を控える。
- VS Code：利用者の最新Stable。API照合は1.142.0（`d956e8a6ac5d904486557eea07e1d6bd62a4d36f`）。実際の版・commitをヘルプのバージョン情報から取得する。
- Jupyter拡張：`ms-toolsai.jupyter`（再現基準2025.9.1）、Python拡張：`ms-python.python`（基準2026.10.0）。既存環境の実際の版を記録する。
- Python：既存のJupyter Pythonカーネル。3.12.13想定、ipykernelは基準6.30.1。正確な版を記録する。初期表示の確認にカーネル起動は不要。
- Node.js：準備スクリプト用。クラウド確認版24.19.0。npm install不要。

1. 上記ブランチを取得し、VS Codeでリポジトリ直下を開く。
2. 実行とデバッグで **TASK-001-01: Cell Toolbar (PROTOTYPE)** を選びF5。標準APIだけの別Extension Development Hostが起動する。`editorInsets` の構成は選ばない。追加のAPI許可フラグは不要。
3. 別Hostのコマンドパレットで **Zizai Probe: Open Empty Notebook** を実行する。
4. 生成先 `dist/toolbar/fixtures/empty.ipynb` が開く。セル0=初期化、1=通常Python（metadataなし）、2=架空処理。全て未実行・出力ゼロ。実際の画面ではセル番号を1始まりで数えるので、初期化は1番目。

F5を使わない場合は、リポジトリ直下から次を個別に実行する。パスが解決できなければextensionDevelopmentPathに絶対パスを指定する。

```sh
node tests/notebook-ui-gate/prepare.mjs toolbar
code --new-window --extensionDevelopmentPath=./tests/notebook-ui-gate/dist/toolbar
```

このモードの試作版は0.0.2。先行実験と拡張IDが同じなので、一度に一つのモードだけ起動する。初期状態に戻す際は別Hostを閉じてprepareを再実行する。ツールバーの場所・hover時の表示・メニューの見た目はVS Code標準の設定に従う。常設のHTML入力欄は作らない。

## ケースと期待結果

2026-10-20の利用者の追加指示により、今回の機能確認はセルツールバーの表示・選択・初期化セルの非表示（T1〜T3）を対象とする。T4の受領済み結果は保持し、標準機能との追加確認T5／T6は未実施のまま後回しとする。以下の定義は後続検証のために残すが、T5／T6の完了を今回の調査終了条件にはしない。既存の画面・操作報告・ログを根拠として利用し、同じログの再送を要求しない。

| ID | 操作 | 合格条件 |
| --- | --- | --- |
| T1 | Pythonを実行せず、通常Pythonセルと処理セルにマウスを合わせる／フォーカスする | セルツールバーに「Zizai（試作）」のメニューボタンが出る。アイコンのみの場合はhoverで名称を確認。開くと「通常Python（試作）」「架空コネクタ（試作）」が選べる。セル全体の標準ツールバー自体が非表示設定なら設定と画面を記録し、API不合格と混同しない |
| T2 | 初期化セルにマウスを合わせ／フォーカスし、通常Pythonセルとの間を行き来する | 初期化セルにはZizaiメニューなし。ほかのセルのフォーカス状態に関係なく通常Python／処理セルにはある |
| T3 | 通常Pythonセルのメニューで架空コネクタを選ぶ。処理セルでは通常Pythonを選ぶ | 選択したセルに対応する通知が出る。コード・metadata・output・実行番号は変わらない。Reportコマンドのsnapshotでセル1のselected=fake、セル2=python。どちらかのセルのコード欄にフォーカスしたまま別セルのメニューも使い、押したセルだけが変わることを確認 |
| T4 | セル2の末尾 `2 + 3` を手動で `2 + 4` に変更し、Jupyter標準▶で実行する | 標準のsourceを編集でき、stdout `probe output` と結果 `6` が標準outputに出る。実行後もセルツールバーのメニューが使え、selectedが維持される。選択操作ではPythonを実行しない |
| T5 | セル2に手動で `raise ValueError("gate-probe")` を追記して標準▶。標準の出力消去も実施 | Python例外は標準outputへ表示。例外後／出力消去後もメニューと選択状態を維持し、初期化セルにはZizaiメニューが出ない |
| T6 | 別タブに切替・復帰、スクロール、標準のコード折りたたみ・展開 | メニューの対象セルが混ざらず再度選べる。表示には標準のhover／ツールバー設定を適用。Notebookを閉じた後の選択値の保存復元は対象外（試作は一時メモリだけ） |

Reportはコマンドパレット **Zizai Probe: Report Toolbar State**。Outputの **Zizai TASK-001-01 Toolbar** に環境版・セル別の選択とMIME・実行順を出す。ログの `toolbar-context-ready` は表示条件設定の完了にすぎず、画面の合格証拠ではない。`selected` は受け取ったセル番号（0始まり）と選択値。

## 返却する情報

```text
実施日／OS・CPU:
ブランチ／git rev-parse HEAD／未コミット差分:
VS Codeの正確な版・commit:
Python拡張版／Jupyter拡張版／カーネルPython・ipykernel版:
F5構成名または実際のCLI:
T1〜T6: 各 合格／不合格／未実施 と実際の結果:
ツールバーの表示設定／hover・フォーカスによる表示の差:
未実行時・実行後・初期化セルの画面:
Zizai TASK-001-01 Toolbar のOutputログ:
Extension HostやDeveloper Toolsにエラーがあればその内容:
```

実データや認証情報は不要。クラウドのロジック検査だけで、これらの画面操作を合格にしない。HTMLフォームの成立やKiro対応まで確認した結果にも拡張しない。
