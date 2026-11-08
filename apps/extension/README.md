# Notebook入力支援の拡張ソース

製品ソースの正本はこのフォルダーです。[TASK-009-01 / #78](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/78)の最初の実装単位として、1項目の選択表示へのマウスオーバーから候補を選ぶ試作を置いています。

## 最初の試作の操作

**対応環境の制限：VS Code安定版1.145.2では、候補へ移動する途中でホバーが消えることを再現しています。** 通常のインストールを変更せず、専用フォルダの1.146.0-insider（commit `29ce94ad8d36c62affc08484e262d5c4fbdd0b3d`）で比較し、連続したマウス移動と保存を挟まない選び直しを確認しました。[比較結果](../../docs/research/notebook-ui/evidence/hover-insiders-20261108.json)を参照してください。これはプレビュー版での限定確認であり、正式な対応版の採用を決定した意味ではありません。

消失はVS Code側の[修正PR](https://github.com/microsoft/vscode/pull/345887)に対応する症状です。選び直しには別の問題があり、最初の確定後も古い版のメニューが残っていました。拡張側で確定後にメニューを閉じ、次のマウスオーバーで現在の状態から開き直すよう修正しました。古いメニューや編集前の要求を拒否する保護は維持しています。

Pythonコードセルの次の雛形で、文字列の左に表示される`[C]`へマウスを置くと、近くのホバーに候補が表示されます。`csv`／`excel`を通常クリックすると対象の文字列だけを書き換えます。同じ場所から選び直せます。Ctrlキーは不要です。

`[C]`はTextEditorDecorationで表示し、セルsourceへは保存しません。候補はHoverProviderで対象文字列に結び付けます。今回の実画面では`[C]`のすぐ上に表示されました。上下の配置はVS Codeが決めます。画面上部のQuickPick・コマンドパレット・Python・カーネルは使いません。他の画面条件・OSは未確認です。

## 入力と責務

`findSelections(source, definitions)`は、先頭行の`%%`マジックと定義中の項目名が一致する代入から、対象文字列の位置・現在値・候補を返します。最初の対象は1行の、JSONとしても解釈可能な二重引用符の文字列です。単一引用符・複数行・式などを勝手に評価・書換えしません。

```text
%%ziz.connector.action.selector
connector.name = "" # この文字列だけを置換対象にする
```

`replaceChoice(source, selection, value)`は、定義にある選択値を引用した文字列として返します。キャンセル・候補外・対象値の変更時は元sourceを返します。この関数自体はNotebookの保存・編集・Python実行を行いません。

`extension.cjs`が表示・ホバーの候補リンク・対象値の編集へ接続します。リンクから実行できるコマンドは拡張自身の値選択に限定し、HTMLは許可しません。セルURIはMarkdown側のURI正規化で変わらないようデータとして符号化して渡し、現在のdocument URIと厳密照合します。`package.json`が開発用拡張の入口、`definitions.json`が同梱候補です。CSV／Excelは候補表示の例であり、業務アクションの採用・実装を意味しません。Notebookの保存はVS Code標準機能を使います。

定義の構造は`magics[マジック名].fields[項目名]`に`label`と文字列配列`choices`を持つ、最初の検討用の形です。公開schema・外部定義の読込・親子候補への対応が完成したという意味ではありません。

## ファイル／フォルダー選択

同じ拡張の次の雛形では、各値の左の`[P]`へマウスを置き、ファイル／フォルダーを選ぶリンクをクリックします。スニペットの作成・登録は利用者担当で、これは入力規約の説明例です。セルのマジック自体を実行する機能はありません。

```text
%%ziz.connector.action.setting
file_path = "" # ファイルの選択例
folder_path = "" # フォルダーの選択例
```

同梱定義では`kind: "file"`／`kind: "folder"`がダイアログの種類を指定します。通常の候補フィールドの`choices`とは分けます。選び直しでは既存値をダイアログの開始位置に渡し、キャンセルした場合は元の値をそのまま残します。

利用者の「OKです。絶対パスで良いです。」により、選択結果はローカルfile URIの**絶対パス**としてコードへ反映します。`replacePath`で文字列として引用し、対象箇所だけを更新します。相対パスへの変換や実行時の基準フォルダーの推測はしません。ファイル内容の読取、独自の実在・権限検査、Python実行はしません。

[実画面の証跡](../../docs/research/notebook-ui/evidence/path-choice-20261108.json)では、専用InsidersとVS Code標準の簡易ファイルダイアログで、file／folderそれぞれの選択・選び直し・キャンセルを確認しました。全6操作の間に保存や別のセル編集を挟まず、最後に標準保存して周囲コードとmetadataを照合しています。OSネイティブダイアログの操作・Remote／WSLは未確認です。

## CLI確認

リポジトリ直下から実行します。追加依存は不要です。

```shell
node --test tests/unit/extension/*.test.cjs
```

## 実画面確認と残りの範囲

[ホバー試作の観測証跡](../../docs/research/notebook-ui/evidence/hover-choice-20261108.json)は、専用プロファイル・架空Notebookでの通常クリック、CSV選択、Excelへの選び直し、標準保存と配置の実測です。初期の失敗・原因切分けと、[以前のCtrl＋クリックの観測](../../docs/research/notebook-ui/evidence/inline-choice-20261108.json)を履歴として保持します。

固定runnerは`tests/e2e/inline-choice.cjs`です。既存の[Playwright調査用依存](../../docs/research/notebook-host/playwright-probe/package.json)を利用します。通常の利用者プロファイルは変更せず、自動確認の終了後は専用ウィンドウと検証用ポートを整理します。`--manual`は`[C]`を表示したところで自動操作を止め、終了合図または利用者による終了まで開いたままにします。待機時間で勝手に閉じません。

外部定義の読込・親子候補、VSIX配布、他環境の対応は未完了です。[要件仕様書](../../docs/features/requirements.md)の未決事項と、拡張限定の開発範囲を参照してください。
