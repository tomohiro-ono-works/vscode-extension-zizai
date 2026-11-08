# Notebook入力支援の拡張ソース

製品ソースの正本はこのフォルダーです。[TASK-009-01 / #78](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/78)の最初の実装単位として、まず`selection.cjs`に副作用のない文字列編集処理を置いています。

## 入力と責務

`findSelections(source, definitions)`は、先頭行の`%%`マジックと定義中の項目名が一致する代入から、対象文字列の位置・現在値・候補を返します。最初の対象は1行の、JSONとしても解釈可能な二重引用符の文字列です。単一引用符・複数行・式などを勝手に評価・書換えしません。

```text
%%ziz.connector.action.selector
connector.name = "" # この文字列だけを置換対象にする
```

`replaceChoice(source, selection, value)`は、定義にある選択値を引用した文字列として返します。キャンセル・候補外・対象値の変更時は元sourceを返します。元Notebookの保存・編集・Python実行は行いません。

定義の構造は`magics[マジック名].fields[項目名]`に`label`と文字列配列`choices`を持つ、最初の検討用の形です。公開schema・外部定義の読込・親子候補への対応が完成したという意味ではありません。

## CLI確認

リポジトリ直下から実行します。追加依存は不要です。

```shell
node --test tests/unit/extension/selection.test.cjs
```

VS Codeへの表示・選択リスト・実際のNotebook編集はまだ接続していません。クリック方法は利用者確認前で、VSIXとして導入可能な段階ではありません。[要件仕様書](../../docs/features/requirements.md)の未決事項と、拡張限定の開発範囲を参照してください。
