# 005 共通契約の確認

正本は `apps/common/contracts/v1/values.schema.json`（JSON Schema 2020-12、ID `urn:zizai:contracts:values:v1`）。`$defs` の `DraftValue`／`DraftValues` は途中入力・省略、`BoundValue`／`BoundValues` は構造の確定した値を表す。

開発環境でリポジトリrootから実行する。

以下のコマンドはエージェントが実行・記録する開発用入口であり、ユーザーへターミナル操作を依頼するものではない。

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

## 005-05：要件対応と検証計画

基準は [開発手順](../../docs/development.md#テスト計画実行時のルール) と [依存関係の区分](../../docs/tasks/task-rules.md#dependency-classification)。進捗・対象commit・実施環境・合否・未確認は [005-05 #40](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/40) が正本。この文書は繰り返し使う定義・操作経路・期待結果を置く。

要件の参照元は [005-03 §C](../../docs/research/contracts/TASK-005-03.md#c-draftvaluesとboundvalues)・[§I](../../docs/research/contracts/TASK-005-03.md#i-005-04に渡す生成収集の受入条件)、[最初の実装計画](../../docs/superpowers/plans/2026-10-24-task-005-contract-assets.md)。C03の要件全体に対して、ここで検証する値構造・生成の部分だけを対応付ける。

### 今回の対象と共通条件

- 担当は全件エージェント。単体は `values.test.mjs` の関数呼出し、API・結合は `assets.test.mjs` のGit・filesystem・生成API／CLI・生成schema消費を実際の操作経路とする。CLI起動という理由でUI検証に分類しない。
- 必須前提は005-04の実装済み値schema・validator・生成／checkと、対応要件・期待結果。対象部分はPR51 `e207d3f`で存在し、各実行ではcheckout commit・差分・Node／npm・OSをIssueへ記録する。003／004の全APIやHost実機はこの単位の条件ではない。
- 開始前にprivate packageのlock導入とschemaの存在を確認する。実行にはNode、Git、一時repoを作成できる領域が必要。秘密値・実データ・外部サービス接続は使わない。
- 証跡はテスト名ごとのassertion結果・合否・件数、必要な生成一覧・hash・manifest。APIケースではexit codeに加えてファイルbytes・差分・入力非変更など各assertionを読む。実行ログはエージェントが採取・分析しIssueから参照する。
- 生成schemaを使うケースも開発側の人工消費例であり、実際のUI／Host／Pythonの実装適合や手動UI合格を示さない。

### ケースごとの対応

| テスト名 | 分類・操作経路 | 目的／期待結果・対応部分 |
| --- | --- | --- |
| `draft_is_not_semantic_validation` | 単体・validator関数 | §C／C03-03の構造部分：途中のtext・json Falseは受理、wrapper欠落・余分キーは拒否。欄の意味検証とは分ける |
| `literal_types_and_precision` | 単体・validator関数 | §C／C03-01の値構造：False・0・null・空値を受理、安全整数域・有限数・decimal正規形を検査 |
| `unset_is_draft_only` | 単体・validator関数 | §C／C03-08の構造部分：欠落と明示unsetを区別し、BoundValuesのunsetを拒否。required/default処理は未対象 |
| `unknown_wrapper_key_and_no_input_mutation` | 単体・validator関数 | §C／§I-1：未知wrapperキー・coercionを拒否、入力非変更、エラーへ値を含めない |
| `variable_names_have_only_structural_validation` | 単体・validator関数 | §C／C03-02の構文部分：ASCII単一名は受理、式は拒否。予約語・存在・実型はこのテストでは判定しない |
| `bad_schema_and_unknown_reference_are_setup_errors` | 単体・validator生成／関数 | §I-1：不正schema・未解決ref・未知の定義名を設定エラーにする |
| `unused_definitions_must_also_be_valid` | 単体・validator生成 | §I-1：未使用・入れ子の定義も未知keyword・refを検査する |
| `cwd_and_paths_do_not_change_output` | API・結合・CLI→Git／生成→出力比較 | §I／C03-07の値資産部分：cwd・日本語／空白で出力不変、manifestのcommit・hash・用途を照合 |
| `stale_extra_and_missing_output` | API・結合・生成／check API→filesystem | §I-3：schema変更・不足・余分をchanged／missing／extraとして区別 |
| `check_is_read_only_and_detects_manifest_changes` | API・結合・check API／CLI→出力比較 | §I-3：manifestの改変も失敗、CLI終了1、検査前後の既存bytes不変 |
| `failed_generation_does_not_publish_manifest` | API・結合・生成API→Git／filesystem | §I-1/2：不正schema・commit・範囲外path・未commit入力を拒否。旧資産保持と新manifest非公開を確認 |
| `symlink_paths_and_entries_are_rejected_without_touching_targets` | API・結合・生成／check API→filesystem | 実装計画の出力境界：symlink拒否・外部target非変更 |
| `cli_rejects_misuse_with_exit_one` | API・結合・CLI引数経路 | 実装計画のCLI：未知操作・欠落／余分な引数を終了1にする。UI操作の証拠ではない |
| `trailing_whitespace_in_repository_name_is_preserved` | API・結合・生成／check API→Git／filesystem | §Iの再現性：repo名の末尾空白を保持して生成・照合する |
| `unused_invalid_schema_definitions_are_never_published` | API・結合・生成／check API→filesystem | §I-1：未使用定義に不正keyword／refがあれば生成前に拒否しmanifestを公開しない |
| `canonical_and_generated_schema_conform_to_value_contract` | API・結合・実生成→schema読込→validator→check | §C／§I-6：正本と生成schemaの両方で同じ人工値14例の受理／拒否・入力非変更を検査。引用符・改行・日本語・末尾backslash・空白、巨大整数・未知キー・省略とunsetを含む |

### 後続の検証経路と開始条件

次の行は実装済みの検証入口・準備完了を意味しない。対象要件に対応する各層の成果を受領し、手順・設定・証跡取得が実在して準備が成功してから実施する。

| 対象・目的 | 分類／実際の操作経路・担当 | 開始条件・期待結果・証跡 |
| --- | --- | --- |
| C03-01/02/08の意味検証・生成値保持、D03-01〜06の定義不整合 | 単体／API・結合。正規化器・生成器・実シグネチャ照合をエージェントが実行 | 005-03／003／004で対象定義・正式APIと期待結果を確定し実装後。引数・値・標準例外とcase結果を採取。今の構造validator合格で代替しない |
| C02-03/05/11/12のmetadata・部分更新・古い応答 | API・結合。002のNotebook API・イベント・保存結果をエージェントが確認 | 002の対象版・実装・D1〜D6の該当根拠と005-02の契約確定後。source／metadata差分・イベント・拒否理由を比較。表示や操作感の合格とは分ける |
| C02-01/02/06/08/13の切替・入力・保存復元・フォーカス、標準▶／Run Allの表示と操作 | 手動UI。ユーザーが実画面を操作し簡単な報告、エージェントが準備・証跡採取・分析・記録 | 現在は未準備・未実施。エージェントが対象版、依存・設定・架空Notebook・log採取、専用ウィンドウと起動終了方法を整え事前確認。準備完了報告とユーザーの開始合図後に小さい操作単位で案内。ユーザーにterminal・設定編集・log整理を依頼しない |
| 合意した範囲のクリック・キー入力と表示状態 | UI自動。Playwrightの画面要素操作をエージェントが作成・保守 | 範囲・開始方法・開始担当が未合意のため未実装・未実施。採用できなければ別方式へ切り替える前に相談。内部関数／状態変更・直接event発火をUI入力経路の証拠にしない。指定された手動UIは別途残す |
| C03-05/07・C02-09のimport・標準カーネル・配布資産の対応 | API・結合。003／006のwheel導入・import・ZIP展開・hash照合をエージェントが実行 | 対象package・カーネル・依存版、006の収集経路確定後。実成果物一覧・hashとmanifest、戻り値・例外を採取。今回の生成schema消費例やCLI成功では代替しない |

手動UIを開始する準備完了の判定には、検証対象と通常作業用ウィンドウの区別、必要数だけの診断ウィンドウ、未保存変更の保護、採取先と終了時の整理方法を含める。待機時間だけでウィンドウを自動終了しない。不具合時は採取済み証跡を分析してから、修正・前回との差・再操作の目的を示す。

結果は経路ごとに合格／不合格／未実施／対象外（理由付き）で記録する。今回のUI経路は未実施であり、API成功から手動UI成功を推測しない。005-05全体の完了は実消費者と必要なUI経路の適合・未確認の扱いを照合して判断する。

## 確認した環境

Node 24.19.0／npm 11.9.0。005のprivateな開発packageでAjv 8.17.1を固定。lockの推移依存はfast-deep-equal 3.1.3、fast-uri 3.1.9、json-schema-traverse 1.0.0、require-from-string 2.0.2。`npm ci --ignore-scripts` で再現導入する。これは製品の最低対応版や脆弱性調査完了の宣言ではない。
