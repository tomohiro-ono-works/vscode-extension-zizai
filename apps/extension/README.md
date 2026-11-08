# Notebook入力支援の拡張ソース

製品ソースの正本はこのフォルダーです。[TASK-009-01 / #78](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/78)の最初の実装単位として、1項目の選択表示から標準候補一覧へつなぐ試作を置いています。

## 最初の試作の操作

Pythonコードセルの次の雛形で、文字列の左に表示される`[C]`をCtrl＋クリックすると、VS Code標準の候補一覧が開きます。`csv`／`excel`を選ぶと対象の文字列だけを書き換えます。同じ`[C]`から選び直せます。これはWindows・既定のリンク操作設定で確認した操作です。他のキー設定・OSは未確認です。

`[C]`は拡張が表示するInlay Hintで、セルsourceへは保存しません。候補一覧は画面上部に出ます。カーソル位置に独自のプルダウンを埋め込む方式ではありません。コマンドパレット・Python・カーネルを使わずに選択できます。

## 入力と責務

`findSelections(source, definitions)`は、先頭行の`%%`マジックと定義中の項目名が一致する代入から、対象文字列の位置・現在値・候補を返します。最初の対象は1行の、JSONとしても解釈可能な二重引用符の文字列です。単一引用符・複数行・式などを勝手に評価・書換えしません。

```text
%%ziz.connector.action.selector
connector.name = "" # この文字列だけを置換対象にする
```

`replaceChoice(source, selection, value)`は、定義にある選択値を引用した文字列として返します。キャンセル・候補外・対象値の変更時は元sourceを返します。この関数自体はNotebookの保存・編集・Python実行を行いません。

`extension.cjs`が表示・標準QuickPick・対象値の編集へ接続します。`package.json`が開発用拡張の入口、`definitions.json`が同梱候補です。CSV／Excelは候補表示の例であり、業務アクションの採用・実装を意味しません。Notebookの保存はVS Code標準機能を使います。

定義の構造は`magics[マジック名].fields[項目名]`に`label`と文字列配列`choices`を持つ、最初の検討用の形です。公開schema・外部定義の読込・親子候補への対応が完成したという意味ではありません。

## CLI確認

リポジトリ直下から実行します。追加依存は不要です。

```shell
node --test tests/unit/extension/*.test.cjs
```

## 実画面確認と残りの範囲

[観測証跡](../../docs/research/notebook-ui/evidence/inline-choice-20261108.json)は、専用プロファイル・架空NotebookでのCtrl＋クリック、CSV選択、Excelへの選び直し、標準保存の結果です。再利用可能な固定runnerは`tests/e2e/inline-choice.cjs`です。既存の[Playwright調査用依存](../../docs/research/notebook-host/playwright-probe/package.json)を利用します。通常の利用者プロファイルは変更せず、終了後に専用ウィンドウと検証用ポートを整理します。

外部定義の読込・親子候補、ファイル／フォルダー選択、VSIX配布、他環境の対応は未完了です。[要件仕様書](../../docs/features/requirements.md)の未決事項と、拡張限定の開発範囲を参照してください。
