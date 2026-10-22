# 開発・ビルド手順の設計案

更新日：2026-10-23。対象：[TASK-006-02](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/42)。

本書は、製品の開発環境・ビルド入口を整備するための設計案である。現在使える導入手順、製品設定の作成許可、動作成立の記録ではない。作業範囲・進捗・確認結果は担当Issueを正本とする。

## 1. 目的と前提

新しいチェックアウトから、個人の絶対パスや既存の作業ディレクトリに依存せず、拡張のVSIXと自作Pythonのwheelを作り、対象版・入力・コマンド・結果を追跡できる状態を目指す。再現性は、固定した環境・依存・ソースから必要な内容の成果物を作れることを指す。ZIP内の時刻等も含めたバイト単位の同一性は初回の要件に追加しない。

[全体設計](01全体設計.md)、[アーキテクチャ](../features/architecture.md)、[配布・対象IDEの判断記録](../decisions/2026-10-22-vscode-distribution-scope.md)、[006-01の環境・配布設計](../research/development/TASK-006-01.md)を入力とする。

- 正式対象はVS Code。Kiroは任意の互換利用で、必須検証には含めない。
- 利用者は既存のVS Code／Jupyter／Pythonカーネルを使用する。追加導入はVSIX、自作wheel、必要なPython依存に収める。
- Git、Node.js／npm、Pythonビルドツールは開発者側の道具とする。利用者へ別途のNode.js／npm、コンパイラ、専用exeインストーラー、独自サーバーを要求しない。
- PythonはJupyterの標準セル実行で評価する。拡張によるpip実行、venv／kernelspec作成、独自実行基盤は設けない。
- 拡張とPythonの版は個別管理し、初回に自動互換性チェックを追加しない。検証した組合せを手順と結果へ記録する。
- UIはTASK-001の[サイドバー設計PR #50](https://github.com/tomohiro-ono-works/vscode-extension-zizai/pull/50)の配置選択を入力とする。006-01で参照した固定版は `4a03b08482fd44f5afb19fb71ac0fa5bd168a0cb`。製品のUI資産構成・操作詳細の確定や動作確認を代替しない。

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
| 正式distribution／import名、ソースとpackageの対応、共通処理と個別処理の境界 | [TASK-003-02 #21](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/21) | pyproject.tomlのpackage収集・検証import |
| 採用処理・引数型・最小依存・認証・外部ソフト条件 | [TASK-004-02 #26](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/26) | runtime依存、対応wheel、設定例・検証条件 |
| UI／Host entry、必要API、GUI資産の読込・ビルド方法 | [TASK-001 #1](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/1)、[TASK-002 #2](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/2) | extension manifest・VSIX収集・F5 |
| 契約の正本と配布表現、生成／同期・陳腐化検査 | [TASK-005-04 #39](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/39) | 契約資産の両配布物への収録 |
| 現行プロジェクトの編集・検証ルールと具体的編集範囲 | AGENTS.mdの必須参照と担当Issue | 対象部分の製品設定作成・検証着手 |
| 対象版と上記依存の導入・ロード確認 | 006-01／006-02 | ツール版の固定、対応条件と再現手順 |

親Task全体の完了を一律の開始条件にしない。必要な対象部分が確定した段階で、その部分の編集範囲と依頼に沿って進める。今回の依頼は006-02の設計・準備であり、製品設定・導入・ビルドへの着手許可を追加しない。

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
