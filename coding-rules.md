<a id="coding-rules"></a>
# コーディングルール

<a id="reference-status-20261102"></a>
## 適用範囲・参照・旧資料（2026-11-02）

本ファイルの配置はリポジトリ直下の `coding-rules.md`。[TASK-006-06 / #71](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/71)で、旧アプリ依存の規則を[現行アーキテクチャ](docs/features/architecture.md)・[開発手順](docs/development.md)・[Taskルール](docs/tasks/task-rules.md)に整合した。これらの既存仕様・Task制約・利用者の承認範囲を上書きせず、個別API・通信・metadata等の未決を本規則だけで正式採用しない。

- 参照パスだけを修正した時点の[規則全文・旧承認・旧参照表記](https://github.com/tomohiro-ono-works/vscode-extension-zizai/blob/46113b95901d7102d3482f1b7c7382c0210974d4/coding-rules.md)を固定commitで保持する。旧日本語化日2026-10-04、旧改訂日2026-10-05、旧 `Status: Current Specification`／`Last verified: 2026-08-21`、TASK-044の決裁表記は原資料の記録であり、本プロジェクトで取得した承認ではない。
- [旧アプリ文書管理資料](docs/research/other-app/documentation-guide.md)と[旧アーキテクチャ](architecture.md)は出典確認用。現在の適用先は[docs入口](docs/README.md)と現行アーキテクチャで確認する。
- 旧資料で参照されていた以下の8リンクは未収録。現在の必須手順から外し、原文の参照表記を下表と固定commitで保持する。類似資料への推測置換や未収録規約の新設は行わない。

| 未収録の旧参照先 | 旧本文中の参照数 |
| --- | --- |
| `../tasks/done/TASK-044/approval-log.md#044-00-20261005-03` | 1 |
| `frontend-libraries.md#vendoring-and-version-record` | 1 |
| `../../tests/manual/README.md` | 1 |
| `data-contract.md` | 1 |
| `connectors.md` | 1 |
| `browser-runtime.md`（support／performanceを含む） | 3 |

旧Remote Safe Gate実行先 `.github/scripts/remote_safe_gate.py` も未収録。旧baseline `8b66fe6` と監査オプションは旧原文の記録として保持し、実行可能な現行コマンドや今回検証済みのGateとして扱わない。別文書 `refactor-policy.md` の所在・規則整備と、新Gateの実装は本作業の対象外とする。

旧依存記述の対応は[本書末尾](#legacy-rule-mapping-20261102)を参照する。実施結果・承認経緯はIssue #71を正本とする。

<a id="before-implementation"></a>
## 実装前の確認

- 着手: 担当Taskと必要な現行仕様・決定・実コードを確認。下記の正本確認と開発サイクルへ進む。
- 仕様変更: Contract・保存形式・Path・Security boundaryの変更は、Taskが仕様変更を許可し、必要な承認がある場合だけ、担当する正本へ実装前に反映。

Taskの変更権限は、明示されたGoal、Scope、Constraints、Acceptance Criteriaに限定する。通常の実装、Bug修正、Refactor、Test追加、検証を理由にCurrent Specificationを変更しない。仕様変更自体がTaskのGoalまたはScopeで承認されている場合だけ、その対象範囲の正本を更新する。

<a id="canonical-source-and-synchronized-copies"></a>
### 正本のソースと同期コピー

- 確認: 変更候補を正本のソース、Application Adapter／統合、vendor／mirror、生成物へ分類。担当する現行仕様で所有者・直接編集の可否・更新経路を確認。名前・pathだけで推測しない。
- 正本: コピーだけのpatchを行わず、担当仕様で定める正本を変更・検証し、その経路で反映。
- 外部upstream: 担当仕様が求めるテスト・取得元commit／版の確定・同期／再vendorを実施。NodeFormの原本・評価patch・テーマCSS・Hostアダプター・生成物と許諾は、[既存の取込条件](docs/research/notebook-ui/TASK-001-02.md)に従って区別する。部品評価を製品への取込・適合完了へ読み替えない。
- 生成物・同一Repository内のコピー: 担当仕様の生成・同期手順と検証を使用。上流commitの条件を一律に追加せず、Task外のcommit・同期を許可しない。
- 不明点: 正本・所有者・更新経路が未確認の場合は、その編集スコープを推測で確定しない。確認済みの独立作業は継続可能。

<a id="development-cycle"></a>
## 開発サイクル

1. 調査・設計: 完了条件から、振る舞い・責務・IF・データの流れ・影響を具体化。詳細設計の範囲は担当Issueと既存設計に従い、[開発手順](docs/development.md)に沿って進める。
2. 評価・承認: 本プロジェクトの[承認境界](docs/README.md#approval-boundaries)に従い、必要な設計判断をまとめて提示。
3. ケース作成: 設計で期待する振る舞いが明らかになった部分から、入力・前提・期待結果・必須条件を作成／追記。設計と並行した草案は可能。正式な合否基準は承認済み仕様と対応付け。
4. 実装・スクリプト整備: 許可された正本を実装。対象IF・期待結果が確定し、検証可能な部分から自動テストと手動実行手順を作成／追記。実装との並行・先行を許容し、担当領域のTest-first条件を維持。問題発生時だけの作成としない。
5. テスト実行: 対象版・必要な実装・定義・環境・個別承認が揃った段階で、変更に必要な単体・結合・環境別・全体の確認を実施。実装時の関連検証を後の全体テストへ先送りしない。
6. 修正・再検証: 結果を先に記録し、Taskが許可する範囲で原因調査・修正・影響範囲の再実行。[検証と実施根拠](#verification-and-evidence)の条件を適用。
7. 完了・リリース: 完了条件と残る影響を確認し、[Taskルール](docs/tasks/task-rules.md)に従って進捗と根拠をIssueへ反映。Task完了・テスト合格・出荷承認・実際のリリースを区別。

- 分割: ケース作成・スクリプト整備・実行は別の成果として管理。大規模な全体テストや開始条件・担当成果が異なる場合は別Subtask。小さなTaskは[Taskルール](docs/tasks/task-rules.md)に従い、同じTask内で区別して記録可能。この開発サイクルとTaskの7工程分類は別に扱う。
- 定義の正本: 再利用する自動テストは既存のテストコード、手動ケース・具体的手順は[tests入口](tests/README.md)から該当する既存ケース・手順を参照する。未収録の旧YAML規約を必須にせず、ケース表・実施ガイド・中間形式で二重管理しない。
- 設計変更: 承認・許可範囲を確認し、担当仕様／必要な設計 → ケース → スクリプト／手順へ影響を反映。対象版・環境・定義版を固定して再検証。実装に合わせた期待結果の無断変更・過去結果の書換えなし。
- 記録: 文書・定義・結果の配置と重複抑制は[Taskルール](docs/tasks/task-rules.md)と[開発手順](docs/development.md)を参照。

<a id="security-quality-target"></a>
## セキュリティの目標品質と比較

- 策定: Codexが、利用前提・保護対象・想定脅威・承認済み条件から、目指す品質と判定可能な基準を具体化。必要な保護、検証方法、対象外の保証、残るリスクを担当Task・必要な設計／仕様へ記録。
- 比較: Jupyter／VS Code等の身近な製品を評価軸ごとの物差しとして使用。自分たちの現状・目標・根拠と比較し、相対位置を説明。
- 条件: 比較対象の版・構成・利用前提、参照した一次資料と確認日を明示。実装済み・検証済み・未確認を分け、条件の違いを説明。
- 位置づけ: 比較対象と同じ品質を満たすことを一律の必須条件にしない。自分たちの目標はTaskの要求と承認済みセキュリティ条件に従って定める。
- 分担: 技術設計・品質の根拠・検証はCodex。オーナーへの提示・判断は[承認境界](docs/README.md#approval-boundaries)に従い、操作・保護方針・残る利用者影響を平易に説明。

## Python

- 変数・関数は`snake_case`、classは`PascalCase`を使用する。
- Connector入口は[現行の責務・呼出し境界](docs/features/architecture.md#dependency-boundaries)と、003／004／005の対象ごとの採用済み宣言に従う。未確定のclass／method／signatureを規約で固定せず、旧共通execute入口を要求しない。
- 通常の戻り値・Python例外はJupyter標準の結果・例外表示へ返す。例外を握りつぶしたり、旧EngineやNode.jsへの独自橋渡しを追加したりしない。
- File pathは対象仕様でbaseと許可範囲を確認し、relative/absolute、traversal、symlinkを区別する。アプリの入力検査とPythonによる実環境の検査は[承認済みの分担](docs/decisions/2026-10-23-python-foundation.md#validation-boundary-20261101)に従い、ファイル存在をアプリ側の生成前提にしない。
- Import時副作用を増やさない。避けられない初期化はTestで隔離可能にする。
- External service、実資格情報、browser/OS操作を通常Testの必須条件にしない。

## JavaScript

- 変数・関数は`camelCase`、classは`PascalCase`、定数は`UPPER_SNAKE_CASE`を使用する。
- `const`を優先し、再代入時だけ`let`を使う。`var`は追加しない。
- 文字列は既存コードに合わせてdouble quote、statementはsemicolon付きとする。
- State計算、DOM描画、UI／Host通信、画面固有処理を混在させず、[現行の責務分離](docs/features/architecture.md#current-responsibility-map)に従う。
- 視覚状態はclass/data属性とCSSで表し、JSへ色値を直書きしない。
- 新しい`window.*` globalは必要最小限とし、UI／Hostの既存境界に従う。旧window.zizPackagesやBridgeを前提にせず、未確定の正式通信形式を推測して固定しない。
- Error logと利用者向け表示を分離し、復旧不能な初期化失敗は継続しない。

<a id="css-and-ui"></a>
## CSSとUI

- 色・テーマは[対象UIの設計](docs/features/notebook-sidebar.md)と採用部品のテーマCSSに従う。旧apps/gui/css/00_tokens.cssを存在する製品資産として要求しない。
- 新規tokenは対象UI・採用部品で確認した責務に沿わせ、未確定の製品ファイル名・token体系を規約だけで追加しない。
- Component CSSは対象componentへ閉じ、global selectorや既存tokenの意味変更を避ける。
- Semantic stateとinteractive stateを混同せず、hover等でerror/successの意味を消さない。
- 既存の非準拠箇所は無関係なTaskで一括修正せず、対象変更時に段階的に解消する。

<a id="data-bridge-and-connector-contracts"></a>
## Notebook・UI／Host・Pythonの契約

- 保存対象は通常の.ipynbのsource・metadata・標準出力であり、[現行の所有・保存境界](docs/features/architecture.md#state-ownership)に従う。旧.zizdの保存・schema・互換期間を導入しない。
- UI／Host通信・metadataとPython呼出し／フォームの境界は[005-02](docs/research/contracts/TASK-005-02.md)・[005-03](docs/research/contracts/TASK-005-03.md)の対象入力と採用状態を照合する。値schemaや案のmain収録だけで正式契約の成立・採用を認定しない。
- [標準Jupyter実行と責務分離](docs/features/architecture.md#dependency-boundaries)を維持し、独自kernel・実行サーバー・Run All・DataFrame同期・旧Bridge Protocolを追加しない。
- 対象となる設定・状態・UI表示・Host更新・Python呼出しを変更する場合は、関係する境界を照合し、一方だけを更新しない。未決API・版・移行・非破壊回復を規則で解決済みにしない。

<a id="reproducibility-and-local-configuration"></a>
## 再現性とローカル設定

- Project内のPathはRepository相対を原則とし、tracked fileへ個人ユーザー名を含む絶対Pathを追加しない。
- 環境依存値は、Repository相対値または安全なdefault、明示的な環境変数またはCLI引数、必要な場合のみignored local configの順で扱う。
- API key、token、password、private key、credential付きURL、browser profile、cookie、sessionをtracked fileへ保存しない。
- 共有可能な設定はsafe exampleとして追跡し、秘密値やPC固有値を含めない。
- Local-only assetが存在しなくても、clone環境でProject仕様、Build、正式Testを理解・実行できる状態を維持する。

<a id="external-dependencies"></a>
## 外部依存

- 対象は、pyproject.toml等の対象Taskで採用した依存宣言・lockで管理するPython package、同梱するthird-party library、今後追加・更新するその他の外部依存とする。未採用のlock形式・vendor配置を旧アプリの名前から推測して必須にしない。
- 外部依存を追加・更新する前に、Projectの利用方法で商用利用が可能か、再配布条件を満たせるか、有償licenseや継続費用が発生しないか、既知の脆弱性がSecurity上受容可能かを確認する。
- 確認結果は、追加・更新を行う対象TaskのEvidenceへ記録する。

<a id="verification-and-evidence"></a>
## 検証と実施根拠

- 対象の識別: 対象commit、環境、定義・期待結果、実行Command、結果を記録。未コミット変更を含む場合は関係するdiff／hash等で区別し、HEADのSHAだけで検証済みと扱わない。詳細は[開発手順](docs/development.md)と[Taskルール](docs/tasks/task-rules.md)へ。
- Python syntaxだけでなく、変更が影響する公開behaviorを検証する。
- YAMLはparse、Pathは実在/拒否境界、移動は旧参照0を確認する。
- 実行方法と判定方法が確定しているTest、Lint、Static check、Buildは、既存Command、Script、Runnerを直接使用する。
- Test実行だけを行う場合は対象Commandと必要なContextへ限定し、FAIL時にTaskの許可なく原因調査、Source変更、再実行を開始しない。
- UIを実画面確認できない場合は、未確認としてTask Evidenceへ記録する。
- Test source/configは追跡し、cache、report、capture、log、node_modules、`.pyc`はartifactとして分離する。
- 成功/失敗の要約をTaskへ残し、長い実行logや画像はartifact path/hashで参照する。
- Remoteへ反映する前に、対象差分への新規credential、個人絶対Path、local-only設定、本文メールの混入を確認する。実credentialは年代を問わずSecurity issueとして扱う。確認した範囲・方法・結果を担当Issueへ記録し、未収録の旧Gateや未実行の全履歴監査を合格扱いにしない。

<a id="browser-runtime-verification"></a>
## 旧Browser Runtimeとの区別

- 旧Browser Runtimeのloopbackサーバー・proof・writer generation・Uvicorn・独自budget／No-Go条件は、原資料の方式であり本プロジェクトの実行基盤・出荷条件へ持ち込まない。
- 現行のUI／Host責務、標準Jupyter実行、テスト分類・開始条件・観測限界は現行アーキテクチャと開発手順に従う。旧Qt／Browser結果、API結果、schema検証を製品UIや指定された手動UIの合格へ流用しない。
- Notebook出力・metadataにはデータが残り得る。認証情報・実データを共有資料・証跡へ残さない。対象の保護境界・許可・採用条件を無断fallback・vendor直接patch・保証縮小で回避しない。

<a id="legacy-rule-mapping-20261102"></a>
## 旧依存記述と現行根拠の対応

旧原文は冒頭の固定commit参照に全て残す。以下は現行規則から外した対象と、その整理根拠である。旧方式の後続実装を作成する一覧ではない。

| 旧依存記述 | 現行での扱い・根拠 |
| --- | --- |
| TASK-044承認・旧Current Specification／検証日・旧READMEによる規約 | 旧出典として保持。現在の承認・Task運用・開発手順を参照し、旧承認を流用しない |
| 共通execute入口・実行Engine・独自error contract | 現行アーキテクチャのPython呼出し・標準結果／例外境界に整合。個別宣言の未決は003／004／005で対象別に照合 |
| Bridge Adapter・window.zizPackages・Bridge Protocol | UI／Host通信と責務分離へ整合。旧Bridgeを必要条件にせず、正式通信契約の未決は保持 |
| .zizd・data-contract／connectors・旧互換期間 | 通常.ipynbと現行の所有・契約境界へ整合。未収録の旧契約を正式仕様としない |
| 固定GUI token・旧token分類・uv.lock／vendor配置 | 対象UI・採用部品のテーマ・対象Taskの依存宣言を参照。旧配置や未採用形式を製品資産として要求しない |
| frontend-libraries・手動YAML規約 | 評価済み部品の原本／patch／許諾と、tests入口・現行テスト分類／手順を参照 |
| 旧Remote Safe Gate・baseline・監査オプション | 未収録の旧実行手順として保持。現行差分の機密等の確認を維持し、新Gateや全履歴監査の実施を認定しない |
| Browser Runtime・loopback／proof・Uvicorn・budget | 旧実行方式として保持。現在の標準Jupyter実行・UI境界・観測と保護の条件へ整合 |
