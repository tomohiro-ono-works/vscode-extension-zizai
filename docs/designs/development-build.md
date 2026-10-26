# 開発・ビルド手順の設計案

更新日：2026-10-27。対象：[TASK-006-02](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/42)。

本書は、製品の開発環境・ビルド入口を整備するための設計案である。現在使える導入手順、製品設定の作成許可、動作成立の記録ではない。作業範囲・進捗・確認結果は担当Issueを正本とする。

## 1. 目的と前提

新しいチェックアウトから、個人の絶対パスや既存の作業ディレクトリに依存せず、拡張のVSIXと自作Pythonのwheelを作り、対象版・入力・コマンド・結果を追跡できる状態を目指す。再現性は、固定した環境・依存・ソースから必要な内容の成果物を作れることを指す。ZIP内の時刻等も含めたバイト単位の同一性は初回の要件に追加しない。

[全体設計](01全体設計.md)、[アーキテクチャ](../features/architecture.md)、[配布・対象IDEの判断記録](../decisions/2026-10-22-vscode-distribution-scope.md)、[006-01の環境・配布設計](../research/development/TASK-006-01.md)を入力とする。

- 正式対象はVS Code。Kiroは任意の互換利用で、必須検証には含めない。
- 利用者は既存のVS Code／Jupyter／Pythonカーネルを使用する。追加導入はVSIX、自作wheel、必要なPython依存に収める。
- Git、Node.js／npm、Pythonビルドツールは開発者側の道具とする。利用者へ別途のNode.js／npm、コンパイラ、専用exeインストーラー、独自サーバーを要求しない。
- PythonはJupyterの標準セル実行で評価する。拡張によるpip実行、venv／kernelspec作成、独自実行基盤は設けない。
- 拡張とPythonの版は個別管理し、初回に自動互換性チェックを追加しない。検証した組合せを手順と結果へ記録する。
- UIはTASK-001の[サイドバー設計PR #50](https://github.com/tomohiro-ono-works/vscode-extension-zizai/pull/50)を入力とする。006-01が先に参照した版は `4a03b08482fd44f5afb19fb71ac0fa5bd168a0cb`。今回受領した更新版 `7127017538f516f9ab54aaa17dfde38b08ad82c7` では操作・状態・通知も承認済みと記録されている。UI方針の再承認待ちには戻さない。製品entry・資産構成、正式契約、実機での成立は別途確認する。

## 2. 方針の比較

| 案 | 利点 | 条件・負担 |
| --- | --- | --- |
| npm＋pip＋標準Pythonビルドfrontend（推奨案） | 一般的な構成で、開発側の道具と利用者の導入を分離できる | NodeとPythonの固定・ビルド入口をそれぞれ管理する |
| uv／Poetry等にPython環境管理を集約 | 環境作成・固定・更新をまとめやすい | 開発者に追加の道具を求め、既存006-01案から運用を変更する |
| 既存の試作準備コマンドを製品入口にする | 試作資産を早く動かせる | 試作用manifest・生成物と製品の正本・配布内容が混在する |

推奨案では、拡張側は同階層のpackage.jsonとpackage-lock.json、Python側はrootのpyproject.tomlと用途別の固定ファイルを使う。新しい統合環境管理ツールやrootのnpm workspaceは初回の必須構成にしない。GUI独自のビルドが必要になった場合は、TASK-001が必要な入口・依存を定義し、006-02が拡張ビルドへ接続する。

## 3. 正本・編集対象・更新経路

今回の文書作業は本書の追加と、[開発手順](../development.md)への案内追加に限る。Issue #42と親Issue #6に現在の許可範囲・結果を記録する。現行仕様、製品ソース、manifest、lock、起動設定、CIは編集しない。

下表は将来の製品整備で確認する具体的な対象候補である。アーキテクチャと各担当Taskの責務に対応付けたもので、表への記載だけでは編集権限を確定しない。

| 対象候補 | 正本・操作の案 | 担当・確定に必要な入力 |
| --- | --- | --- |
| `apps/extension/package.json`、`apps/extension/package-lock.json` | 製品manifest・開発コマンドの正本を新規作成。lockは依存解決から更新し、手編集しない | 006-02が構成・固定を整備。TASK-001／002がUI・Hostのentry、contributions、activation、使用APIを定義 |
| `apps/extension/.vscodeignore` | VSIXへ含めるファイルの制御を新規作成し、梱包後の一覧と照合 | 006-02。必要なHost・UI・契約・license資産の一覧を各領域から受領 |
| `pyproject.toml` | Python配布metadata・依存宣言・package収集の入口をrootに新規作成 | 006-02がビルド設定へ統合。TASK-003-02がdistribution名／import名／ソース対応、TASK-004が採用処理と実行依存を定義 |
| `requirements/build.in`、`requirements/test.in` | 開発側ビルド／テスト用の直接依存の入力を新規作成 | 006-02と各領域の既存テスト入口を照合。Python実行依存はpyproject.tomlから取得し、別の手書き正本を作らない |
| `requirements/build-win-amd64-cp314.txt`、`requirements/test-win-amd64-cp314.txt`、`requirements/runtime-win-amd64-cp314.txt` | 対象環境で解決した全依存の固定版・SHA-256を収録する生成物の候補 | 006-02。入力・生成コマンド・対象環境を記録。正式対象が変われば名前・対象を再設計 |
| `.vscode/tasks.json`、`.vscode/launch.json` | 製品のbuild／F5項目を追加。既存の試作・診断項目と名前・extensionDevelopmentPathを区別 | 006-02が入口を統合。製品entryとUI資産が必要。既存設定の削除や試作終了は範囲に含めない |
| `docs/development.md`、`tests/manual/development-build.md` | 確定した導入・確認入口とデスクトップ手順を記載 | 006-02。実行前の設計例を成立済みコマンドとして案内しない |
| `config/` の非機密設定例 | 製品が実際に読む設定項目が決まった場合だけ、ファイル名と読込責務を特定 | 読込を担当するTaskと協調。006-02で独自の設定形式・認証経路を追加しない |

`apps/core/`、`apps/connectors/`の正式なモジュール・内部import・実装・単体テストはTASK-003／004、`apps/common/`の正本・言語別表現・生成／同期はTASK-005の担当である。006-02はそれらを収集し、領域側の確定済みテスト入口を呼び出す。生成物だけを直接修正しない。ビルド補助スクリプトが必要な場合は、処理・正本・対象ファイルを追加設計してから編集範囲へ含める。

006-01の基準版では、AGENTS.mdが必須参照とする `docs/features/coding-rules.md` と `docs/features/refactor-policy.md` は未収録である。canonical-source preflightの未確認事項を解消し、対象部分の所有者・更新経路を確認してから製品の編集範囲を確定する。rootの旧アプリ由来coding-rules.mdを代替採用しない。

## 4. 環境と依存を固定する方法

006-01のWindows x64／通常ABIのCPython3.14.3は最初の検証基準候補である。最低対応版、全OS対応、ネイティブ依存のロード成功を示さない。Node.js／npmの観測版とExtension Host内Node.jsの版は別に記録する。Node・npm・Python・pip・ビルドfrontend／backend・VS Code・Python／Jupyter拡張の具体版は、製品整備時の確認結果に基づいて手順へ明記する。

拡張の新規導入ではpackage-lock.jsonを入力にnpm ciを使う案とし、通常の再現確認でlockを更新しない。VSIX作成用の `@vscode/vsce` もプロジェクトの開発依存に固定し、npm scriptから呼び出す。グローバル導入や実行時の最新版取得を入口にしない。

Pythonでは次の3種類を分離する。

| 固定集合 | 内容 | 使用先 |
| --- | --- | --- |
| build | pipの準備版、build frontend、setuptools等のbackendと全推移依存 | 新規の専用ビルドvenv |
| test | 各領域が採用したPythonテストツールと全推移依存 | 新規の検証用venv。runtimeと合わせて解決可能な組合せにする |
| runtime | pyproject.tomlの採用アクションに必要な直接依存と全推移依存 | 対象OS／Pythonでwheelを検証する環境 |

固定ファイルには全推移依存の厳密版と対象wheelのSHA-256を含める。更新時は、正本の依存変更、対象環境での解決、固定ファイル作成、クリーン環境での導入・pip checkを一組で記録する。lock生成の具体的なコマンドは製品依存とツール版を確定するときに指定する。現在の個人環境のpip freezeや、006-01の比較用30件のdry-run結果を製品lockへ転用しない。

Pythonビルドは、専用venvへ固定済みビルド依存を導入した上で、`python -m build --wheel --no-isolation` を使う案とする。build-system.requiresとbackendが追加要求する依存も固定集合へ含める。不足時の自動取得や依存検査の無効化で通さない。第三者依存は適合wheelを使い、利用者側でのソースビルドを前提にしない。

runtimeとtestの同時導入も版・hashを保ち、相互に矛盾する固定集合を別々のpip実行で上書きしない。自作wheelの検証では、先に固定runtimeを導入し、自作wheelを `--no-deps` で追加してpip checkと対象importを確認する。これは固定環境でのビルド確認用手順である。利用者向けには、選択カーネルに対応するPythonで自作wheelと必要依存を手動導入する別の手順を用意する。

## 5. 開発・ビルド・デバッグの入口案

以下は製品設定作成後の入口案であり、現在実行できる手順ではない。パッケージ名・テストrunner・固定版を推測したコマンドは作らない。

| 段階 | 入口・作業ディレクトリの案 | 期待結果 |
| --- | --- | --- |
| 対象版の取得 | 新しいチェックアウトのcommitと未コミット差分を記録 | 個人環境の生成物を引き継がない |
| Node依存の導入 | repo rootから `npm --prefix apps/extension ci` | manifestとlockが一致し、追跡ファイルに変更なし |
| Pythonビルド環境 | rootで対象Pythonから専用venvを作成し、対応build固定集合をhash検査付きで導入 | 実際のPython・pip・frontend／backend版が記録できる |
| 契約同期 | TASK-005-04が指定する正本・生成／同期コマンドと陳腐化検査を呼ぶ | 指定入力と両配布表現が一致。必要な入力不足・古いコピーを検出 |
| 拡張ビルド | `npm --prefix apps/extension run build` を新設 | Host entryと必要UI・契約資産を配布ディレクトリへ収集 |
| 単体・契約確認 | 各領域の確定済みrunnerをnpm scriptまたは対象Pythonから呼ぶ | 実施ケース・結果を記録。製品テストがない状態を0件合格にしない |
| VSIX | `npm --prefix apps/extension run package:vsix` を新設し、固定したvsceのpackage処理を呼ぶ | 必要資産・licenseを含む1つのVSIX。梱包前に製品buildが必ず走る |
| 自作wheel | rootで専用ビルドvenvのPythonから `python -m build --wheel --no-isolation` | core・connectors・必要な定義資産を含む1つの自作wheel |
| 配布物の静的確認 | VSIX／wheelを展開せず一覧とmetadataを確認 | 第6節の収録条件に一致 |
| クリーン導入・import | ソースcheckout外のcwd、別の新規検証venvで作成済みwheelを導入 | 正式import名とimport元が導入先を指す。ソースが偶然見えて成功する状態を除外 |
| 製品F5 | `ZizAI: Product` を追加候補名とし、製品buildをpreLaunchTaskに接続 | 製品entryをExtension Development Hostで読み込む |

拡張のbuildとVSIX作成が同じ資産収集処理を使うようにし、F5専用の手動コピー手順を作らない。ビルド時には、当該処理が所有する生成先だけを再作成し、古いファイルを残さない。削除対象の絶対パスが所有する生成先内にあることを確認する。

F5は製品の `apps/extension/` を候補のextensionDevelopmentPathとし、`tests/.../dist/`を参照する既存試作設定とは区別する。Pythonの選択・実行はJupyterに委ねる。F5時に依存導入やNotebookセル実行を行わず、初回準備を明示的な別手順にする。製品サイドバーの動作と、Notebookの標準実行・保存・再オープンは対象版のデスクトップで確認する。標準機能の追加確認に関する既存の保留条件も担当Issueに従う。

## 6. 配布物・設定・失敗時の条件

| 対象 | 含めるもの | 混入を検出するもの |
| --- | --- | --- |
| VSIX | 製品manifest、Host entry、必要なUI・契約資産、該当LICENSE／NOTICE | 試作拡張、テストfixtures、秘密値、個人絶対パス、Python本体、不要な開発依存 |
| 自作wheel | 正式Pythonモジュール、必要な契約・定義資産、配布metadata、該当license情報 | Host／GUI、試作、cache、実データ、認証情報、ソースcheckout依存 |
| 生成ディレクトリ | 対象buildが再生成できる資産 | 手動修正、他Taskの正本、古い資産の残留 |
| 非機密設定例・証跡 | 読込責務が確定した項目のダミー値、版・結果・必要なhash | credential、個人の実パス、実データ・Notebook出力 |

自作wheelは純Pythonを目指すが、依存全体がOS非依存とは扱わない。license宣言のmetadata確認と、実際の配布資産内のLICENSE／NOTICE・ネイティブ同梱物の確認を区別する。元コネクタの再利用許諾も確認する。

各段階は非0終了、入力不足、契約不一致、資産欠落を失敗として停止し、その先の成果物を合格扱いにしない。記録には対象commit・環境・コマンド・終了値・ログ参照を含める。失敗後の調査・修正・再試行は当該Taskの許可範囲に従う。別の依存版を無記録で入れ直して通さない。

## 7. 部分ごとの開始条件

| 必要な入力 | 提供元 | 入力後に具体化できる範囲 |
| --- | --- | --- |
| `zizai-runtime`／`zizai`と責務別ソース対応は設計入力として受領済み | [TASK-003-02 #21](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/21)、PR #53の固定版 | 下記§7.1の明示収集案。個別モジュール一覧と契約資産は対象部分の確定後に追加 |
| 採用処理・引数型・最小依存・認証・外部ソフト条件 | [TASK-004-02 #26](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/26) | runtime依存、対応wheel、設定例・検証条件 |
| UI／Host entry、必要API、GUI資産の読込・ビルド方法 | [TASK-001 #1](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/1)、[TASK-002 #2](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/2) | extension manifest・VSIX収集・F5 |
| 契約の正本と配布表現、生成／同期・陳腐化検査 | [TASK-005-04 #39](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/39) | 契約資産の両配布物への収録 |
| 現行プロジェクトの編集・検証ルールと具体的編集範囲 | AGENTS.mdの必須参照と担当Issue | 対象部分の製品設定作成・検証着手 |
| 対象版と上記依存の導入・ロード確認 | 006-01／006-02 | ツール版の固定、対応条件と再現手順 |

親Task全体の完了を一律の開始条件にしない。必要な対象部分が確定した段階で、その部分の編集範囲と依頼に沿って進める。今回の依頼は006-02の設計・準備であり、製品設定・導入・ビルドへの着手許可を追加しない。


### 7.1 受領したPython構成と収集設定案

[PR #53のPython設計](https://github.com/tomohiro-ono-works/vscode-extension-zizai/blob/d058a287aae1ddb33ed34d0422a286697dd79f70/docs/research/python-import/TASK-003-02.md)と[了承範囲の記録](https://github.com/tomohiro-ono-works/vscode-extension-zizai/blob/d058a287aae1ddb33ed34d0422a286697dd79f70/docs/decisions/2026-10-23-python-foundation.md)を受領した。命名・ソース対応を「入力待ち」から「受領済みの設計入力」へ更新する。PRの統合・製品編集許可や依存版の確定とは区別する。

| 配布先 | 正本となるソースの設計入力 | 収集条件 |
| --- | --- | --- |
| distribution `zizai-runtime` | root `pyproject.toml` | 名称をproject.nameへ反映する。公開レジストリへの登録は含まない |
| `zizai/` | `apps/core/src/zizai/` | 親packageの__init__.pyはcore側だけが所有 |
| `zizai/core/` | `apps/core/src/zizai/core/` | 個別アクションや全SDKの一括importを置かない |
| `zizai/connectors/` | `apps/connectors/src/zizai/connectors/` | 003／004が定義する実モジュールを収集。親zizaiを二重所有しない |
| Python向け契約資産 | 005-04が確定する生成先 | 配布先package・資産一覧・読込方法は未確定。仮のpackage名を追加しない |

setuptoolsの明示package列挙とpackage-dirで、上記の分かれた正本を1つのwheelへ対応付ける案とする。次は**収集設定だけのTOML断片**であり、製品pyproject.tomlではない。project／build-systemの完全なmetadata・依存・版・license・契約資産を省略しているため、このままビルドする手順にはしない。

```toml
[tool.setuptools]
packages = ["zizai", "zizai.core", "zizai.connectors"]

[tool.setuptools.package-dir]
"zizai" = "apps/core/src/zizai"
"zizai.connectors" = "apps/connectors/src/zizai/connectors"
```

zizai.coreは親の対応先配下から収集する。採用コネクタが単一の.pyではなくsubpackageを持つ場合は、その実在するpackageを明示リストへ追加する。自動探索でapps/全体を含めない。生成契約packageも正式名と出力が確定してから収集表へ追加する。断片の構文確認は、setuptoolsでのビルド・wheel内容の適合確認を代替しない。

版の管理元は、Pythonをrootのproject.version、拡張をapps/extension/package.jsonのversionとする静的管理を推奨する。実際の初回版は未選定。配布のために手書きソースをimportして版を取得したり、個別コネクタの初期化を走らせたりしない。バージョンAPIを公開するかは003が定め、006が新しい公開APIを追加しない。

003へ渡せる配布側条件は、root配布設定、上記の明示収集、1自作wheel、選択カーネルへの手動導入、配布物からのimport確認である。package入口だけの設計に全アクションの確定を要求しない。実際のpackage入口作成・最小wheelの検証も、具体的な編集範囲・適用ルール・導入／ビルド着手の許可が揃ってから行う。

PR #53の更新版では、003自身の最小単位を3つのpackage入口とし、他領域の完了を一律に待たず設計できること、U01〜U10の独立確認ケースが具体化された。006は配布metadata・3入口の収録・checkout外からの導入条件を対応付け、import時にSDKを読み込まない動作の正本・テストは003へ任せる。最小入口だけの確認に、全アクションやPython向け契約packageの完成を要求しない。全採用処理を同梱する製品wheelの完成とは分けて記録する。

### 7.2 契約資産の収集と配布記録

[PR #51の005-02 §9](https://github.com/tomohiro-ono-works/vscode-extension-zizai/blob/a2b563c7dd543b8aed8584655da08b8ab3e5da7c/docs/research/contracts/TASK-005-02.md#9-005-04へ渡す正本生成同期配布案)を収集側の設計入力として受領した。生成先は候補であり、正式schema・生成器・実行コマンドはまだない。

- 005の生成manifestは、正本ファイルの相対path・SHA-256、生成器版、生成元commit、用途別の出力一覧を対応付ける。
- 006の収集では、そのmanifestと生成結果を照合してから、Host／UI用をVSIX、必要最小のPython用をwheelへ含める。UI通信・Notebook編集用schemaをPythonへ一律収録しない。
- 005-04が指定する再生成・陳腐化検査で、欠落、古い入力hash、生成先の余分なファイルを失敗にする。006は正式な生成コマンドを受領して呼び出し、別の生成器を作らない。
- ビルド・配布記録には、対象ソースcommit、拡張版、Python版、ツール・lock識別、契約入力manifestのhash、成果物ごとの相対ファイル名・SHA-256、確認結果を記録する。絶対パス・credentialは不要。
- 成果物hashは梱包が終わってから外部の配布記録へ記載する。成果物自身のhashをその成果物内へ埋め込む循環を作らない。契約の入力manifestと完成物の配布記録は役割を分ける。

配布記録の正本は006側、契約入力・生成manifestの正本は005側とする案で、製品の正式なファイル名・schemaは未確定。ZIPへの配置と最終導入確認は006-05へ渡す。実行時にHostからカーネルへ接続する版チェックは追加しない。

### 7.3 受領入力間の差と影響範囲

次の比較はPR #53の `d058a287aae1ddb33ed34d0422a286697dd79f70` とPR #51の `a2b563c7dd543b8aed8584655da08b8ab3e5da7c` に対するもの。相手の文書・判断履歴を変更済みとは扱わない。PR更新時は対象部分だけ再照合する。

| 対象 | 003の了承済み設計入力 | 005の現行案・判断記録 | 006での扱い |
| --- | --- | --- | --- |
| distribution／import | zizai-runtime、zizai.core／zizai.connectors | zizai-notebook、zizai_core／zizai_connectorsの候補 | 配布名・収集対応は003の設計入力へ合わせる。契約module表・初期化例との一致確認は未達 |
| Python向け生成package | 正式名・生成先は005-04の入力待ち | zizai_contracts／build/contracts/python配下が候補 | 名称を独自確定せず、収集対象からの欠落・重複確認を後続へ残す |
| Pythonの用途 | 通常Pythonセル、専用Pythonコネクタは設けない | 用途待ち・初回7種類／16候補の記載が残る | 003の回答を受領。採用個別処理の数・依存・テスト対象の最終一覧は004／005との整合後に固定 |
| 新規未設定時のsource | 処理コードを生成せず、未設定用raiseを加えない | ValueErrorを生成し標準Run Allを停止する回答を記録 | 利用者回答の記録が相違。006で一方を選ばず、この動作に依存する契約・生成テスト・統合期待結果を確定しない |
| サイドバー | 通常Pythonとの区別は関連領域で整合 | PR #50更新版の操作・状態・通知を承認済みとして受領 | UI方針の再承認を待たず、製品entryと正式契約の入力を待つ |

未設定sourceの判断の相違は、distribution名・ソース配置の設計を進める妨げにはしない。一方、実装・契約テストの期待結果は担当領域で判断記録と対応仕様を整合するまで保留する。006でCurrent Specificationや別Taskの判断を上書きしない。

## 8. 製品整備時の受入確認

1. 対象commitの新しいチェックアウトから固定依存を導入し、追跡manifest・lockに変更が出ない。
2. 同じ入口から製品build・各領域の対象テスト・VSIX・wheel作成が実行でき、必要ファイルが揃う。
3. checkout外のcwdでwheelの導入先importを確認でき、pip checkが成功する。依存metadataと固定runtimeが対応する。
4. 生成契約・UI資産の古いコピー、欠落、試作・秘密値・個人パスの混入を検出できる。
5. 製品F5と試作F5の起動先が区別でき、製品F5に必要な事前準備を手順だけで再現できる。
6. 対象commit・環境・コマンド・期待結果・実際の結果をIssueから追跡できる。空白・日本語を含む別のcheckoutパスでも個人絶対パスに依存しないことを確認する。

006-02の完了条件「新しいチェックアウトで導入・ビルドできる手順と結果」は、設計文書だけでは満たさない。CIの継続実行は006-04、全採用アクションのNotebook統合は006-03、ZIPの任意展開先からの手動導入・出荷判断材料は006-05へ渡す。本書の設計例を、それらの実施結果として数えない。

## 9. コマンドの根拠

2026-10-23に一次資料で入口・オプションを確認。文書の最新版と製品で固定するツール版を区別し、006-01のpip25.3での比較dry-runも製品導入結果とは区別する。

- [npm ci](https://docs.npmjs.com/cli/v11/commands/npm-ci/)：既存lockを使い、manifest不一致時に失敗し、manifest・lockを更新しない。
- [VS CodeのVSIX作成・導入](https://code.visualstudio.com/api/working-with-extensions/publishing-extension)：vsce packageによるVSIX作成と、Marketplace公開を伴わない導入。
- [PyPA buildの基本操作](https://build.pypa.io/en/stable/how-to/basic-usage.html)：wheel作成、no-isolation、必要なビルド依存の事前導入。
- [pipの再現可能な導入](https://pip.pypa.io/en/stable/topics/repeatable-installs/)と[hash検査・wheel限定](https://pip.pypa.io/en/stable/topics/secure-installs/)：厳密版・全依存hash・適合wheelを用いる固定方法。

- [setuptoolsのpackage列挙・package-dir](https://setuptools.pypa.io/en/latest/userguide/package_discovery.html)と[pyproject設定](https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html)：実ディレクトリとimport階層が異なる場合の明示対応。今回のTOML断片の根拠であり、製品のビルド結果ではない。


## 10. 共通ルールの反映と新しい受領入力

2026-10-26のmain入力 `8d4098acc7156eac6b5b5e53a52ddf8571a61f9e` には、承認済みサイドバー設計、002の診断・研究、003の最小Python基盤・既存9件・検証分類が含まれる。006側へ取り込み、共通文書ではVS Code正式対象とサイドバー・共通選択メニュー・下書き表示を保持した。006の今回の反映対象は設計・研究・検証計画であり、新しい製品manifest・lock・起動設定・UI操作は追加しない。

2026-10-27にmain `d40e24665c97495f4dea8f184e33758d2e550690` の004設計チェックポイントも受領した。通常Pythonと専用6コネクタ、表型pandas.DataFrame、Excelのchunk_size=0は分割なしという判断を入力に含める。一方、採用API・フォーム資産・型変換の残項目、BigQuery認証、依存版・利用許諾は未確定で、実処理・外部接続・配布物の検証結果ではない。比較用30wheelの集合を正式runtime lockへ流用しない。

依存の現在の区分・工程別の充足根拠は006-01〜05のIssueに記載し、本書の相互参照だけで一律に開始を止めたり、既存の必須条件を外したりしない。[TASK-006の検証計画](task-006-verification.md)で実際の操作経路と担当を区別する。PlaywrightのUI自動ケースは範囲・開始方法・開始担当の事前合意後、手動UIは準備成功の報告とユーザーの開始合図後に行う。起動方法やAPIの成功で手動UIの合格を代替しない。

003のPR #55 `5f7e5d194ae4da53c9e002f7f9501a17d0d82b56` に、rootのpyproject.tomlと最小3packageの実装がある。配布名zizai-runtime、開発版0.0.0.dev0、Requires-Python >=3.12、最小実行依存なし、setuptools.build_metaの明示収集である。本文の「新規作成」「未選定」は当初の設計段階を表す。006で別のpyprojectを先に作らず、003の正本・更新経路と統合する。これは全採用コネクタを含む製品全体の依存・正式対応範囲・出荷版の確定ではない。

003の既存runnerは隔離Pythonの -I からbackend・pipを読めるビルド環境を必要とする。ユーザーsiteにだけbackendがある通常Pythonを、専用ビルド環境と同一視しない。専用venvでのWindows独立9件再確認を受領し、環境前提を006の設計に反映する。006では導入・ビルドを再実行していない。

005のPR #51 `e207d3f59e49905e0e786a5301d55cbb56b0465e` に、values.schema.jsonと生成／check CLIの第1単位がある。正本→build/contracts/js/values.schema.json、manifest.jsonの収集条件とbuild前check終了0を受領した。Python生成資産・正式action等は未提供。本文§7.3の比較は旧固定版の履歴であり、現行案ではzizai-runtime／zizaiと通常Python・専用6コネクタを受領済み。未設定sourceの異なる判断の影響は対象契約での整合事項として残し、この値構造単位に混在させない。
