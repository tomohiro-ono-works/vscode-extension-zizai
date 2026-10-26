# TASK-005 共通の値契約・生成資産 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 実行方法は利用者の選択後に適用する。

**Goal:** 005-04の最初の単位として、フォーム値の共通schemaと、正本から生成した資産の更新漏れ・改変・余分なファイルを検出する開発用入口を整備する。

**Architecture:** 値の構造を `apps/common/contracts/v1/values.schema.json` の単一正本とし、Host／UIへ渡すJSON資産を決定的に生成する。検証・生成ツールとそのテストは005が所有し、Notebook API、Python生成器、業務アクション、VSIX／wheelのbuildへは接続しない。

**Tech Stack:** JSON Schema 2020-12、JavaScript ESM、Node標準test runner・crypto・fs。validator候補はAjv 8.17.1を開発ツールの依存として固定する。今回取得したNodeは24.19.0／npm 11.9.0であり、製品の最低版を意味しない。

**Spec:** [005-02の契約設計](../../research/contracts/TASK-005-02.md) §9〜10、[005-03の値・生成設計](../../research/contracts/TASK-005-03.md#contract-draft-20261023) §C・D・I。計画の開始入力はPR #51の `a2b563c7dd543b8aed8584655da08b8ab3e5da7c` と本計画に伴う005資料の整合差分。

**状態・範囲:** 利用者の「では、005で進められる範囲で進めてください。」を受け、この計画の2 Task／10手順を実装済み。値schema・private開発ツール・テストだけを追加し、15件のテストと実際の生成／checkを確認した。独立レビューの未使用定義検証・末尾空白pathの2指摘は再現テストで修正。005-04全体は未完了で、他Task・Notebook実行・配布設定・CIは変更していない。実施結果と残作業の正本はIssue #39。

## Global Constraints

- 正式対象はVS Code、Kiroは任意参考。独自実行基盤・DataFrame同期・起動時の拡張対Python互換性チェックは追加しない。
- UIがPython sourceを生成しない。下書きはmetadata、確定値とsourceはHostが管理し、Pythonの実行・戻り値・例外は既存Jupyterに委ねる。
- VSIXと自作Pythonのwheelを1つのZIPで配布する既存方針を維持する。利用者へNode／npm・生成器・ビルドツールを要求しない。
- 正本だけを編集し、生成資産を独立編集しない。既存の試作・他領域のソース・root配布設定・CI・現行仕様をこの単位で変更しない。
- 作業状態は既存Issue #5／#37〜40が正本。新しいTask実行記録Markdown・Issueは作らない。
- `docs/features/coding-rules.md` と `docs/features/refactor-policy.md` は未収録。旧アプリのルート規約を自動適用せず、AGENTS.md・docs入口・Taskルール・契約設計と、次の005専用条件をこの単位の実装基準としてIssue #39へ明記する。全体規約の新設は005で行わない。
- 005専用条件：値検証で入力を変更しない、通常ログへ値を出さない、外部ref・任意コードを動的取得しない、依存をprivateな開発packageとlockへ限定する、生成・削除は指定repoのbuild/contracts内だけ、checkは読取専用、変更ごとに仕様に対応するテストと実結果を残す。
- 未設定sourceの動作、専用Pythonの扱い、個別API・型・初期値の照合は、以下の値構造／生成処理の独立した入力条件にはしない。

## Review Focus

2026-10-25追補：mainの5bbb234／fa21803を現在の作業ブランチへmergeし、[依存分類](../../tasks/task-rules.md#dependency-classification)・[テスト分類と担当](../../development.md#テスト計画実行時のルール)を適用する。Issue #37〜40の現在の依存関係欄を必須の前提条件／相互確認先／区分未確定へ整理し、必要成果・対象工程・充足状況・独立範囲を記録する。初回実装の結果履歴は維持する。

005-05は実装済みの値契約・生成資産を対象に反復する。[tests/contracts/README.md](../../../tests/contracts/README.md#005-05要件対応と検証計画)へ各caseの目的・分類・実操作経路・期待結果と共通の担当・対象版・開始条件・証跡を対応付ける。validator関数は単体、Git／filesystem・CLI・実生成schema消費はAPI・結合でエージェントが実施する。UI自動はPlaywrightとし範囲・開始方法・担当の事前合意後、手動UIはエージェントが環境・証跡採取を準備して完了報告し、ユーザーの開始合図後にユーザーが操作する。ユーザーへターミナル操作・ログ整理を依頼せず、API・自動の成功を手動UI合格にしない。現時点でUIの準備・実行は行っていない。

1. DraftValueの途中不正は保存できるが、wrapper構造不正は拒否する。Task 1の `draft_is_not_semantic_validation` で区別する。
2. None・False・0・省略、巨大整数を同一視しない。Task 1の `literal_types_and_precision` と `unset_is_draft_only` で固定する。
3. 任意のcwdや日本語・空白pathで同じ入力が同じ資産になる。Task 2の `cwd_and_paths_do_not_change_output` で固定する。
4. 検査コマンドが古い生成物を修復して成功を装わない。Task 2の `check_is_read_only` と `stale_extra_and_missing_output` で固定する。
5. 生成失敗後に以前のmanifestが最新として使われない。Task 2の `failed_generation_does_not_publish_manifest` と、006へ渡すbuild前検査条件で固定する。

---

## 0. 対象部分と開始ゲート

| 区分 | この計画で行うもの | 後続へ分けるもの |
| --- | --- | --- |
| 値構造 | DraftValue／BoundValueと値map、再帰JSON literal、既知wrapperの未知キー拒否 | fieldIdの登録表照合、必須・範囲・非表示・default解決などアクションに依存する意味検証 |
| 生成・検査 | 値schemaの正規化JSON、生成manifest、再生成比較 | メッセージ／metadata／ActionDefinition schema、UI／Host投影、TS型生成、Python契約資産 |
| 配布受渡し | `build/contracts/js/` の生成物一覧と入力／出力hash | VSIX／wheel収集・導入・CI・ZIP。005の生成物を消費する後続作業として渡す |

実装前に、次の条件を005の既存Issueへ記録する。これらが満たされる前は文書計画の状態を維持する。

- [ ] 値契約の対象部分と、本計画の編集ファイル・更新経路を005-04 #39へ明示する。
- [ ] 現行規約の未収録と、Global Constraintsにある005専用の適用条件をIssue #39に記録する。実装対象に関係する上位ルールが追加された場合は差を確認する。全体規約の整備や他Taskの完了を一律の待ち条件にしない。
- [ ] この計画のレビューと実行方法を確認する。005-04全体、005-05の適合合格、現行仕様変更、PRのmergeまで一括承認されたとは扱わない。

003／004の親Task全体完了、Hostの実機D1〜D6、Pythonの全シグネチャ確定をこの単位の開始条件へ追加しない。値構造と純粋な生成処理は単独で検証できる。

## 1. ファイル・所有者・一方向の更新

下記は実装時の追加対象。今回これらを作成した意味ではない。

| ファイル | 所有・責務 |
| --- | --- |
| `apps/common/contracts/v1/values.schema.json` | 005の値構造の唯一の手書き正本。`$id` は `urn:zizai:contracts:values:v1`、`$schema` は2020-12 |
| `scripts/contracts/package.json`・`package-lock.json` | 005専用のprivateな開発ツール依存。Ajvを `8.17.1` に固定。製品manifestやPython依存へ混在させない |
| `scripts/contracts/validation.mjs` | Ajv2020で値schemaを検証する。型coercion・default注入・余分なキーの自動削除をしない |
| `scripts/contracts/assets.mjs` | 入力収集、正規化JSON、hash・manifest、出力比較。Notebook・カーネルに依存しない |
| `scripts/contracts/cli.mjs` | `generate`／`check` のCLI。CLI失敗は終了1、成功は0 |
| `tests/contracts/values.test.mjs` | 値構造・精度・途中入力とwrapper不正の境界 |
| `tests/contracts/assets.test.mjs` | 同一生成・古い／不足／余分な出力・検査の非変更性・失敗時の状態 |
| `tests/contracts/README.md` | 実装後に、実在する確認入口と製品適合との限界を記載 |

`build/contracts/js/values.schema.json` と `build/contracts/manifest.json` は生成物。正本→assets.mjs→buildの一方向で更新する。作業ディレクトリを変えても入力path・hashはrepo相対の同じ値とし、絶対path・現在時刻・利用者名を生成dataへ入れない。

Ajv候補の根拠：[v8.17.1 package.json](https://github.com/ajv-validator/ajv/blob/v8.17.1/package.json)、[2020-12入口](https://github.com/ajv-validator/ajv/blob/v8.17.1/lib/2020.ts)を読取確認した。配布metadataはMIT宣言。設計時は読取確認のみ。実装ではprivate開発packageへ固定し、lock生成・ignore-scriptsでの再導入・構造検証を実行した。脆弱性や配布条件の精査完了は宣言しない。生成時に第三者ソースを製品へコピーしない。

## Task 1: 値schemaと構造validator

**Files:** 上表のvalues.schema.json、package／lock、validation.mjs、values.test.mjs、README。

**Interfaces:**

- Consumes: `createValuesValidator(schema: object)` に渡す、単一のvalues.schema.json。
- Produces: `(name: "DraftValue" | "BoundValue" | "DraftValues" | "BoundValues", value: unknown) => ValidationResult`。
- `ValidationResult` は `{ok:true}` または `{ok:false, errors:Array<{path:string, keyword:string}>}`。入力の値・stackを返却／通常ログへ含めない。未知name・不正schemaは呼出し前の設定エラーとしてthrowする。
- 構造検査であり、Python変数の存在・実型・action固有の意味・source生成は扱わない。

### schemaの実装条件

- `$defs` に `JsonValue, DraftValue, BoundValue, DraftValues, BoundValues` を定義し、同じ形をコピーしない。
- DraftValueはtext（kind＋text）、json（kind＋value）、unset（kindのみ）の排他的な3形。途中のtext `"-"` は妥当な下書き。
- BoundValueはliteral（kind＋value）、integer（kind＋decimal）、variable（kind＋name）の3形。unsetはない。
- wrapperは必須キーを要求し、余分なキーを拒否。literal内の業務JSON objectのキーまで固定する意味ではない。
- JsonValueはstring／boolean／null／有限number／再帰array／string-key object。整数は `-9007199254740991`〜`9007199254740991`。任意精度integerはdecimal文字列として表す。
- decimalの正規形は `0` または先頭ゼロのない符号付き十進整数。`+1`・`01`・`-0`はBoundValueでは拒否し、DraftValueのtextから正規化する後続処理と分ける。
- variable.nameはASCII単一名の構造を検査する。Python予約語の対象版との照合は後続の意味検証で行い、構造検査だけを正式なPython引数の検証完了にしない。
- Ajv2020は `strict:true, strictNumbers:true, allErrors:true, coerceTypes:false, useDefaults:false, removeAdditional:false`。外部refのネットワーク取得を組み込まない。

- [x] **Step 1: `values.test.mjs` の失敗テストを書く。**

  `draft_is_not_semantic_validation` は `{kind:"text",text:"-"}` と `{kind:"json",value:false}` をDraftValueとして許し、`{kind:"text"}`・`{kind:"unset",value:null}` を拒否する。V03-06の「integer欄へFalse」は意味検証の後続ケースであり、DraftValue構造として拒否しない。

  `literal_types_and_precision` はliteral False・0・null・空string・空arrayを別の値のまま許し、literalの `9007199254740992` と `Infinity` を拒否する。`{kind:"integer",decimal:"9007199254740993"}` を許し、decimal `"01"` と `"-0"` を拒否する。

  `unset_is_draft_only` はDraftValuesの空object・unsetを許し、BoundValuesのunsetを拒否する。`unknown_wrapper_key` はliteralにmethodキーを足した入力を拒否し、入力object自体が検証で書き換わらないことをdeepEqualで確認する。

- [x] **Step 2: `node --test tests/contracts/values.test.mjs` を実行し、validator／schema未作成による失敗を確認する。** 意図した失敗理由を記録する。
- [x] **Step 3: privateな開発packageとlock、schema、`createValuesValidator` を実装する。** packageの追加は005ツールだけ。初回のlock作成後は `npm --prefix scripts/contracts ci --ignore-scripts` を再現導入の入口にする。
- [x] **Step 4: 同じtestコマンドで全件PASSを確認する。** 不正schema・未知refの設定エラーも失敗として確認する。Node／npm・直接／推移依存の実版を記録する。
- [x] **Step 5: Task 1のファイルだけをcommitする。** READMEに「構造validatorであり、actionの意味・実機適合は別」を記載する。

## Task 2: 一方向生成と非変更のcheck

**Files:** assets.mjs、cli.mjs、assets.test.mjs、README。Task 1のschemaを参照し、生成コピーを手修正しない。

**Interfaces:**

- Consumes: Task 1の `createValuesValidator` とschema正本、`{repoRoot:string, outputRoot:string, sourceCommit:string}`。
- Produces: `generateAssets(options): Promise<Manifest>`、`checkAssets(options): Promise<{ok:boolean, differences:Array<{path:string, reason:"missing"|"extra"|"changed"}>}>`。
- manifestの欄は `manifestVersion:1, generatorVersion:"0.1.0", schemaDialect:"2020-12", sourceCommit, inputs, outputs, actions`。generatorVersionは開発ツール版で、拡張／Python配布版とは別。
- inputsは `{path,sha256}`、outputsは `{path,sha256,consumers:["host","gui"]}` の配列。pathは入力／出力root内の相対path。actionsはこの単位では空配列。未採用actionや架空Pythonシグネチャを製品catalogに登録しない。
- CLIはrepoRootをスクリプト自身の配置から求め、outputRoot既定値をrepo内のbuild/contractsとする。`generate --source-commit <40桁hex>`／`check --source-commit <40桁hex>` を受け付ける。

- [x] **Step 1: `assets.test.mjs` の失敗テストを書く。**

  `cwd_and_paths_do_not_change_output` は日本語・空白を含む一時Git repoに人工schemaをcommitし、その実際のcommit IDをsourceCommitに使う。異なるcwdから、同一schema・同一sourceCommitで2回生成し、出力バイト列とmanifestを比較する。テスト用repoは製品履歴から独立させる。

  `stale_extra_and_missing_output` はschema変更、出力1つの削除、余分なJSONの追加を別々に行い、checkがchanged／missing／extraを区別することを確認する。

  `check_is_read_only` は改変前後の出力一覧・各ファイルのbytesが不変で、check終了1となることを確認する。

  `failed_generation_does_not_publish_manifest` は不正schema・不正sourceCommit・範囲外pathで失敗し、新しい有効manifestを公開しないことを確認する。

- [x] **Step 2: `node --test tests/contracts/assets.test.mjs` を実行し、生成処理未作成による失敗を確認する。**
- [x] **Step 3: assets.mjsとcli.mjsを実装する。** 入力を検証してから空の一時出力へ生成する。JSONはUTF-8・LF・安定キー順とし、意味のある配列順は保持する。manifest自身をoutputsのhash対象へ含めない。

  sourceCommitが示す正本のbytesと作業中の入力bytesを照合し、不一致を拒否する。Gitは開発側の確認に使い、利用者の実行依存へしない。未知schema・未解決refはネットワークで補わない。出力先は当該repoRootのbuild/contractsに限定し、repoRoot自体や範囲外path・symlink経由の出力先を拒否する。テストも一時repoRoot内の同じ配置を使う。

  generateは成功した一時出力だけで指定出力rootを更新する。失敗時に以前の資産が残っていても最新生成成功とは扱わず、006へ渡すbuildはcheck終了0を必須条件にする。checkは一時生成結果との完全比較だけを行い、既存出力を更新しない。

- [x] **Step 4: `node --test tests/contracts/values.test.mjs tests/contracts/assets.test.mjs` で全件PASSを確認する。** CLIのusage不正、欠落sourceCommit、改変検出で終了1も確認する。
- [x] **Step 5: Task 2のファイルだけをcommitし、READMEを更新する。** 正本をcommitした状態で、生成・checkの実コマンドと実結果を記録する。

実装後に確認したコマンド（開発側の入口。生成・checkは指定commitに正本が記録されていることが必要）：

```sh
npm --prefix scripts/contracts ci --ignore-scripts
node --test tests/contracts/values.test.mjs tests/contracts/assets.test.mjs
node scripts/contracts/cli.mjs generate --source-commit "$(git rev-parse HEAD)"
node scripts/contracts/cli.mjs check --source-commit "$(git rev-parse HEAD)"
```

## 2. 005-04／05と利用側への完了受渡し

Task 1／2の完了は、値構造と生成物の独立確認が成立した範囲だけを示す。005-04全体の完了には、messages・cell-metadata・form-definition・action定義の対象確定、意味検証・UI／Host投影・必要なPython資産の生成、正本との一意な対応が別途必要。

005-05は実装された対象schema／生成器に対して初めて適合を判定する。005-02の実行世代やNotebook編集の原子性が、この値schema合格で解決したことにはしない。005-03の値の正規化も、構造validatorとは分けて後続単位にする。

005が利用側へ渡すものは、schema ID・参照先、生成元commit、manifestと出力一覧、実行済みコマンド・結果、残る未実施、変更時の再生成／check手順。Host・UIやPythonのファイルを005で変更せず、必要な契約資産だけを担当側へ渡す。配布packageの実装、CI、実機、外部接続・業務処理はこの計画の対象外。

## 3. 計画の自己照合と残る条件

値構造の境界・精度・未知キーはTask 1、生成・入力hash・非変更の検査・失敗時の扱いはTask 2に対応付けた。Review Focusの5件は各Taskの具体テストへ対応する。定義名・関数名・manifest欄は上記のInterfacesを正とし、後続Taskで別名を使わない。

未設定source・Pythonの個別API／型・採用action・Hostの編集整合／実行観測は、この計画の外側に残す。005専用の適用条件・編集範囲をIssueに記録し、この計画の第1単位を実装・検証した。全体規約の未収録を製品全体の完了と取り違えず、独立した005の値契約の一律停止理由にもしない。
