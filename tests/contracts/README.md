# 005 共通契約の確認

正本は `apps/common/contracts/v1/values.schema.json`（JSON Schema 2020-12、ID `urn:zizai:contracts:values:v1`）。`$defs` の `DraftValue`／`DraftValues` は途中入力・省略、`BoundValue`／`BoundValues` は構造の確定した値を表す。

開発環境でリポジトリrootから実行する。

```sh
npm --prefix scripts/contracts ci --ignore-scripts
node --test tests/contracts/values.test.mjs
node --test tests/contracts/values.test.mjs tests/contracts/assets.test.mjs
```

`scripts/contracts/validation.mjs` の `createValuesValidator(schema)` は定義名と値を受ける検証関数を返す。成功は `{ok:true}`、失敗は `{ok:false,errors:[{path,keyword}]}`。値を変更せず、エラーに値を含めない。名前・schemaの設定不正は例外になる。外部refの取得は行わない。エラーのpathはキー名を含むため、通常ログへフォームの値や検証結果を丸ごと出さない。

これは構造validatorであり、actionの意味・変数の存在や実型・Python予約語・source生成・実機適合は別の検証。途中の `-` やjsonのFalseは妥当な下書きで、入力欄の意味検証は後続の正規化で行う。有限数の整数は安全精度内に限定し、巨大整数はdecimal文字列で保持する。

利用者の実行環境へNode／npm／この開発packageを追加する手順ではない。

## 生成・更新漏れの検査

正本を編集してcommitした後、その実在する40桁commitを指定する。生成元commitの正本bytesと作業中のbytesが一致しなければ失敗する。Gitは開発側だけで使用する。

```sh
node scripts/contracts/cli.mjs generate --source-commit "$(git rev-parse HEAD)"
node scripts/contracts/cli.mjs check --source-commit "$(git rev-parse HEAD)"
```

CLIは自身の配置からrepoを求めるため、別cwdから絶対pathで呼び出しても同じ資産になる。成功は終了0、設定不正・入力不一致・検査差分は終了1。通常ログには値・schema内容・任意のファイル名を含めない。APIの `checkAssets({repoRoot,outputRoot,sourceCommit})` は差分の相対pathと `missing`／`extra`／`changed` を返し、既存ファイルを変更しない。

| 生成先（repo相対） | 内容 |
| --- | --- |
| `build/contracts/js/values.schema.json` | Host／GUI向けschema。同じIDと `$defs` を持ち、例えば `urn:zizai:contracts:values:v1#/$defs/BoundValue` を参照する |
| `build/contracts/manifest.json` | schema版、生成器版、生成元commit、入力・出力のSHA-256、利用側、空のactions |

正本→開発生成器→生成資産の一方向で更新する。生成コピーを手で編集しない。JSONはUTF-8／LF／安定したキー順で、配列順は保持する。入力hashは正本の元bytes、出力hashは生成後のbytes。manifest自身はhash一覧から除くが、checkの完全比較には含む。絶対path・時刻・利用者名を含めない。空のactionsは個別Python APIの採用を意味しない。

出力先は指定repoの `build/contracts` だけ。symlink経由のpath・出力内のsymlink・特殊ファイルを拒否する。入力を検証後、出力root内の空の一時directoryへ生成し、成功した内容だけを反映してmanifestを最後に配置する。同じ出力rootへの生成・検査・消費は直列に実行する。反映中断時に以前の資産や一部のファイルが残っても生成成功とは扱わず、**利用側のbuildはcheck終了0を必須条件**にする。checkは修復を行わない。不足・改変・余分なファイル／空directoryも検出する。

この単位はHost／GUIへのJSON資産の入口まで。messages・metadata・フォーム定義・action、意味検証、Python資産、VSIX／wheelへの収集、CI接続、実機適合は別途。配布担当へは正本ID／commit・manifest・2出力と、build前check必須の条件を渡す。

## 確認した環境

Node 24.19.0／npm 11.9.0。005のprivateな開発packageでAjv 8.17.1を固定。lockの推移依存はfast-deep-equal 3.1.3、fast-uri 3.1.9、json-schema-traverse 1.0.0、require-from-string 2.0.2。`npm ci --ignore-scripts` で再現導入する。これは製品の最低対応版や脆弱性調査完了の宣言ではない。
