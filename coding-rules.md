<a id="coding-rules"></a>
# コーディングルール

日本語化日: 2026-10-04（表記変更）。従来の見出しへの参照を維持。

- 改訂日: 2026-10-05。開発サイクル・正本の更新経路・品質策定を[TASK-044の決裁](../tasks/done/TASK-044/approval-log.md#044-00-20261005-03)に基づき統合。

- Status: Current Specification
- Last verified: 2026-08-21

<a id="before-implementation"></a>
## 実装前の確認

- 着手: 担当Taskと必要な現行仕様・決定・実コードを確認。下記の正本確認と開発サイクルへ進む。
- 仕様変更: Contract・保存形式・Path・Security boundaryの変更は、Taskが仕様変更を許可し、必要な承認がある場合だけ、担当する正本へ実装前に反映。

Taskの変更権限は、明示されたGoal、Scope、Constraints、Acceptance Criteriaに限定する。通常の実装、Bug修正、Refactor、Test追加、検証を理由にCurrent Specificationを変更しない。仕様変更自体がTaskのGoalまたはScopeで承認されている場合だけ、その対象範囲の正本を更新する。

<a id="canonical-source-and-synchronized-copies"></a>
### 正本のソースと同期コピー

- 確認: 変更候補を正本のソース、Application Adapter／統合、vendor／mirror、生成物へ分類。担当する現行仕様で所有者・直接編集の可否・更新経路を確認。名前・pathだけで推測しない。
- 正本: コピーだけのpatchを行わず、担当仕様で定める正本を変更・検証し、その経路で反映。
- 外部upstream: 担当仕様が求めるテスト・取得元commit／版の確定・同期／再vendorを実施。Frontend libraryは[取り込み契約](frontend-libraries.md#vendoring-and-version-record)を維持。
- 生成物・同一Repository内のコピー: 担当仕様の生成・同期手順と検証を使用。上流commitの条件を一律に追加せず、Task外のcommit・同期を許可しない。
- 不明点: 正本・所有者・更新経路が未確認の場合は、その編集スコープを推測で確定しない。確認済みの独立作業は継続可能。

<a id="development-cycle"></a>
## 開発サイクル

1. 調査・設計: 完了条件から、振る舞い・責務・IF・データの流れ・影響を具体化。詳細設計の文書化は[必要な条件](../README.md#detailed-design-documentation)に限定。
2. 評価・承認: [評価レベルと承認境界](../README.md#approval-boundaries)に従い、必要な設計判断をまとめて提示。
3. ケース作成: 設計で期待する振る舞いが明らかになった部分から、入力・前提・期待結果・必須条件を作成／追記。設計と並行した草案は可能。正式な合否基準は承認済み仕様と対応付け。
4. 実装・スクリプト整備: 許可された正本を実装。対象IF・期待結果が確定し、検証可能な部分から自動テストと手動実行手順を作成／追記。実装との並行・先行を許容し、担当領域のTest-first条件を維持。問題発生時だけの作成としない。
5. テスト実行: 対象版・必要な実装・定義・環境・個別承認が揃った段階で、変更に必要な単体・結合・環境別・全体の確認を実施。実装時の関連検証を後の全体テストへ先送りしない。
6. 修正・再検証: 結果を先に記録し、Taskが許可する範囲で原因調査・修正・影響範囲の再実行。[検証と実施根拠](#verification-and-evidence)の条件を適用。
7. 完了・リリース: 完了条件と残る影響を確認し、[進捗と根拠](../README.md#progress-and-handoff-information)をTaskへ反映。Task完了・テスト合格・出荷承認・実際のリリースを区別。

- 分割: ケース作成・スクリプト整備・実行は別の成果として管理。大規模な全体テストや開始条件・担当成果が異なる場合は別Subtask。小さなTaskは[文書管理](../README.md#task-and-subtask-separation)に従い、同じTask内で区別して記録可能。
- 定義の正本: 再利用する自動テストは既存のテストコード、手動ケース・具体的手順は[手動テスト規約](../../tests/manual/README.md)のYAML。ケース表・実施ガイド・中間形式で二重管理しない。
- 設計変更: 承認・許可範囲を確認し、担当仕様／必要な設計 → ケース → スクリプト／手順へ影響を反映。対象版・環境・定義版を固定して再検証。実装に合わせた期待結果の無断変更・過去結果の書換えなし。
- 記録: 文書・定義・結果の配置と重複抑制は[テストと実施根拠](../README.md#tests-and-execution-evidence)を参照。

<a id="security-quality-target"></a>
## セキュリティの目標品質と比較

- 策定: Codexが、利用前提・保護対象・想定脅威・承認済み条件から、目指す品質と判定可能な基準を具体化。必要な保護、検証方法、対象外の保証、残るリスクを担当Task・必要な設計／仕様へ記録。
- 比較: Jupyter／VS Code等の身近な製品を評価軸ごとの物差しとして使用。自分たちの現状・目標・根拠と比較し、相対位置を説明。
- 条件: 比較対象の版・構成・利用前提、参照した一次資料と確認日を明示。実装済み・検証済み・未確認を分け、条件の違いを説明。
- 位置づけ: 比較対象と同じ品質を満たすことを一律の必須条件にしない。自分たちの目標はTaskの要求と承認済みセキュリティ条件に従って定める。
- 分担: 技術設計・品質の根拠・検証はCodex。オーナーへの提示・判断は[承認境界](../README.md#approval-boundaries)に従い、操作・保護方針・残る利用者影響を平易に説明。

## Python

- 変数・関数は`snake_case`、classは`PascalCase`を使用する。
- Connector入口は`execute(action, params, context)`を維持する。
- 例外を握りつぶさず、利用者向けerror contractまたは実行Engineへ返す。
- File pathはbaseと許可範囲を明示し、relative/absolute、traversal、symlinkを区別する。
- Import時副作用を増やさない。避けられない初期化はTestで隔離可能にする。
- External service、実資格情報、browser/OS操作を通常Testの必須条件にしない。

## JavaScript

- 変数・関数は`camelCase`、classは`PascalCase`、定数は`UPPER_SNAKE_CASE`を使用する。
- `const`を優先し、再代入時だけ`let`を使う。`var`は追加しない。
- 文字列は既存コードに合わせてdouble quote、statementはsemicolon付きとする。
- State計算、DOM描画、Bridge Adapter、page固有処理を混在させない。
- 視覚状態はclass/data属性とCSSで表し、JSへ色値を直書きしない。
- 新しい`window.*` globalは必要最小限とし、既存`window.zizPackages`/Bridge boundaryを優先する。
- Error logと利用者向け表示を分離し、復旧不能な初期化失敗は継続しない。

<a id="css-and-ui"></a>
## CSSとUI

- 色は`apps/gui/css/00_tokens.css`の既存tokenを使用する。
- 新規tokenは既存のbrand/semantic/interactive/surface/text/border/alpha責務へ分類する。
- Component CSSは対象componentへ閉じ、global selectorや既存tokenの意味変更を避ける。
- Semantic stateとinteractive stateを混同せず、hover等でerror/successの意味を消さない。
- 既存の非準拠箇所は無関係なTaskで一括修正せず、対象変更時に段階的に解消する。

<a id="data-bridge-and-connector-contracts"></a>
## データ・Bridge・コネクタの契約

- `.zizd`とschemaは[データの契約](data-contract.md)を正とする。
- Connectorの共通境界は[コネクタの契約](connectors.md)を正とする。
- Bridge Protocol変更は[アーキテクチャ](architecture.md)とADRの互換期間に従う。
- Configの宣言、state、renderer、backend actionを変更する場合は、一方だけを更新しない。

<a id="reproducibility-and-local-configuration"></a>
## 再現性とローカル設定

- Project内のPathはRepository相対を原則とし、tracked fileへ個人ユーザー名を含む絶対Pathを追加しない。
- 環境依存値は、Repository相対値または安全なdefault、明示的な環境変数またはCLI引数、必要な場合のみignored local configの順で扱う。
- API key、token、password、private key、credential付きURL、browser profile、cookie、sessionをtracked fileへ保存しない。
- 共有可能な設定はsafe exampleとして追跡し、秘密値やPC固有値を含めない。
- Local-only assetが存在しなくても、clone環境でProject仕様、Build、正式Testを理解・実行できる状態を維持する。

<a id="external-dependencies"></a>
## 外部依存

- 対象は、`pyproject.toml`/`uv.lock`で管理するPython package、`apps/gui/vendor/`等へ同梱するthird-party library、今後追加・更新するその他の外部依存とする。
- 外部依存を追加・更新する前に、Projectの利用方法で商用利用が可能か、再配布条件を満たせるか、有償licenseや継続費用が発生しないか、既知の脆弱性がSecurity上受容可能かを確認する。
- 確認結果は、追加・更新を行う対象TaskのEvidenceへ記録する。

<a id="verification-and-evidence"></a>
## 検証と実施根拠

- 対象の識別: 対象commit、環境、定義・期待結果、実行Command、結果を記録。未コミット変更を含む場合は関係するdiff／hash等で区別し、HEADのSHAだけで検証済みと扱わない。詳細は[テストと実施根拠](../README.md#tests-and-execution-evidence)へ。
- Python syntaxだけでなく、変更が影響する公開behaviorを検証する。
- YAMLはparse、Pathは実在/拒否境界、移動は旧参照0を確認する。
- 実行方法と判定方法が確定しているTest、Lint、Static check、Buildは、既存Command、Script、Runnerを直接使用する。
- Test実行だけを行う場合は対象Commandと必要なContextへ限定し、FAIL時にTaskの許可なく原因調査、Source変更、再実行を開始しない。
- UIを実画面確認できない場合は、未確認としてTask Evidenceへ記録する。
- Test source/configは追跡し、cache、report、capture、log、node_modules、`.pyc`はartifactとして分離する。
- 成功/失敗の要約をTaskへ残し、長い実行logや画像はartifact path/hashで参照する。
- Remoteへ反映する前に、正式なRemote Safe Gateで新規credential、個人絶対Path、local-only設定、本文メールの混入を確認する。Historical Baseline以前の既知情報は通常Gateの失敗理由にしないが、実credentialは年代を問わずSecurity issueとして扱う。
- 通常Gateは`python .github/scripts/remote_safe_gate.py --push-base <remote-base>`で実行する。Baseline `8b66fe6`以降のPrivacy全履歴監査は`--mode audit --baseline 8b66fe6`、全履歴credential監査はこれに`--all-history-secrets`を加えて明示実行する。

<a id="browser-runtime-verification"></a>
## Browser Runtimeの実装・検証参照

- 詳細正本: [Browser Runtime](browser-runtime.md)。loopback実port Host／route別Origin／session＋独立client proof／writer generationをhandler・作用／配送直前に検査。socket排他やCORS／cookieだけで認可しない。
- HTTP／Application／Browser console／起動・計測は機械的codeと非機密metadata。Uvicorn access log OFF、秘密・URL全文・本文・自由UI detail・request echoなし。診断・計測も既定OFF／redaction。旧save traceを流用しない。
- [独立Browser Riskとsupport](browser-runtime.md#verification-support)、[数値budget期限](browser-runtime.md#performance)を後続Taskで検証。required未実施／FAIL／Blocked／Skip・stale証跡・budget未承認はNo-Go。旧Qt PASS・schema validationを実Runtime成立と扱わない。
- Current Specification先行とcanonical更新経路を維持。CSP／cookie／native不成立を無断fallback・vendor直接patch・保証縮小で回避せず、影響と根拠をownerへ戻す。
