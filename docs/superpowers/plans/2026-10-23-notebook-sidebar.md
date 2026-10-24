# Notebook Sidebar Implementation Plan — 前提整理版

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** セルの「設定」で1つのサイドバーを使い回し、セル別下書き・確定・対象表示を備えたUIを、標準Notebookのコード・実行・保存と共存させる。

**Architecture:** UIは表示と入力、Extension Hostは対象セル・metadata・source更新、TASK-005は正式な境界契約を所有する。標準WebviewViewを表示面とし、UI内の状態計算とNodeForm描画を分離する。評価用Webviewの仮メッセージを製品契約へ昇格させない。

**Tech Stack:** JavaScript、HTML/CSS、VS Code標準WebviewView、既存の固定NodeForm候補。単体検査にはNode組込み `node:test` を候補とする。製品のmanifest・module形式・runner・依存版は環境側の確定前に導入しない。

**Spec:** [Notebookのサイドバー設定UI](../../features/notebook-sidebar.md)。利用者は2026-10-23に「そうですね。進めてOKです。」と回答し、UI動作の書面を承認した。

**Readiness:** **製品実装へは未移行。** 本文は依存成果とUI内部の分割を具体化した準備版。正式な契約・適用規約・製品の起動入口がなく、Host統合の確定シグネチャと再現コマンドをまだ記述できない。下記G1〜G3を満たして実装計画を改訂・レビューするまで、製品コードを作成しない。

## Global Constraints

- 「セルをクリックしただけでは設定対象を変えない。」
- 「入力ごとにHostへ下書きを通知し、Hostが対象セルのmetadataを更新する。Python sourceは変更しない。」
- 「Notebookファイルへの永続化は標準保存に従い、独自のディスク自動保存は追加しない。」
- 「同じセルのコネクタ／アクション変更は既存仕様どおり、以前の確定値・下書きを破棄して新しい初期状態にする。」
- 「更新成功の応答まで確定成功を表示しない。処理中の同じ確定要求は重複送信しない。」
- 「フォーム値・選択パス・sourceを環境報告や診断ログへ追加しない。」
- 正式対象はVS Codeのみ。Kiroは任意の参考利用で、必須検証・出荷条件ではない。[既存の利用者判断](https://github.com/tomohiro-ono-works/vscode-extension-zizai/blob/40db82f55483f403c311bddea087ef3765e0ba1f/docs/decisions/2026-10-22-vscode-distribution-scope.md)を引き継ぐ。
- 標準APIによる通常起動を基準とし、提案APIやInsidersを必須にしない。最低VS Code／Node版を実機の観測版だけから決めない。
- Python生成・実行・OS操作をUIへ置かない。標準のセル実行・Run All・出力・例外表示を利用する。
- UI動作の承認、実装計画の承認、関連Taskの編集範囲、PR統合、製品・出荷の完了を区別する。

## Review Focus

1. 同名Notebookとセル移動：表示番号が変わっても別セルに確定しない。G1の識別例と後続のHost結合試験で確認する。
2. 削除直後のUndoとタブ終了：同じ参照が戻る／NotebookDocumentが残る場合も古い要求を復活させない。G1で寿命・世代の規則を定めてからケース化する。
3. 下書き保存中の別セル選択と保存失敗：旧対象と値を維持し、保存成功を推測しない。UI状態・Host結合の双方で検査する。
4. 非表示・再表示・サイドバーへのフォーカス移動：単なるフォーカス移動で対象を失わず、別Notebookなら編集不可にする。状態試験とVS Code実機を分ける。
5. 古いファイル選択・確定応答と連続クリック：旧応答を新しいフォームへ適用せず、確定を重複送信しない。契約例・状態試験・実OS選択で確認する。

## 基準と所有者

- 設計の承認対象はPR #50の `4a03b08482fd44f5afb19fb71ac0fa5bd168a0cb`。本計画の追加で承認範囲を拡大しない。
- `apps/gui/`・`apps/extension/`・`apps/common/` は基準版では各 `.gitkeep` のみ。既存製品コード・正式契約・root package.json・製品runnerは存在しない。
- UIの正本責務はTASK-001、WebviewView登録・Notebook操作はTASK-002、通信とmetadataはTASK-005、manifest／起動／配布はTASK-006。下記のファイル案を名前だけで編集許可済みとしない。
- `tests/nodeform-reuse/` は評価用正本、`dist/` は生成物。NodeFormは上流固定版・patch・テーマCSSを分離している。製品へコピーする際は正式な取得・同期・license配置を先に定める。
- PR #49と#50はREADME・全体設計・UI設計・architectureに重なる。統合時は「VS Codeのみ正式対象」と「サイドバー配置」の両方を保つ。今回どちらもmergeしない。
- 他Taskが使用する `task-002-01-desktop/` の診断クローン、既存試作ブランチ、元の未追跡資料を編集しない。

## 実装前に必要な入力

| Gate | 必要な具体的成果 | 担当・現在の状態 | この計画からの要求 |
| --- | --- | --- | --- |
| G1 正式契約 | セル／Notebook／要求の識別、設定世代、draft／commitの要求応答、未知・不正入力、取消・失敗・遅延応答、metadata所有範囲と保存規則を、正式な正本と例で一意に参照できる | [TASK-005-02 #37](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/37)は未着手。TASK-005-04の契約資産も未整備 | A→B→A、同じセルのアクション変更、保存失敗、削除→Undo、最後のタブ閉鎖、古いOS選択結果の期待応答を渡す。新しい正式キー・wire形式をTASK-001で先取りしない |
| G2 適用規約 | AGENTSが示す `docs/features/coding-rules.md` と、正本・外部部品・生成物の更新、検証と失敗時の扱いを本プロジェクト向けに確認できる | mainの参照先は404。ルートの同名資料は旧Engine／Bridge等を含む。旧承認を移植しない | 対象を文書整備として明示し、既存のWorking Agreements・責務・承認済み条件に合う規約を整えることが必要 |
| G3 Host・開発入口 | 対象部分のHost境界、manifestの正本、module形式、再現可能なテスト／F5設定、NodeFormの固定取込経路 | [TASK-002-02 #15](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/15)、[TASK-005-04 #39](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/39)、[TASK-006-02 #42](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/42)の成果は今回の計画基準にない | 関連する対象部分を受け取る。親Task全体の完了待ちにはせず、未確定のpackage／コマンドを推測しない |

G1／G2を整備する作業は、現時点のTASK-001のUI文書範囲を超えるため、次のスコープ判断が必要。今回の書面承認をその着手許可へ読み替えない。

## ファイル分割案

この表はG1〜G3を受けて具体化する設計候補。製品の作成許可・既存runnerへの接続を確定する表ではない。

| 候補 | 正本責務と更新経路 |
| --- | --- |
| `apps/gui/sidebar/state.mjs` | UI内部の状態計算。Hostから受けた表示状態と入力状態を扱い、metadataやセルAPIは持たない |
| `apps/gui/sidebar/presenter.mjs` | DOM表示、NodeFormのmount／destroy、入力・検証・確定の通知 |
| `apps/gui/sidebar/styles.css` | VS Codeテーマ変数を使うサイドバー内の配置と状態表示 |
| `tests/unit/sidebar-state.test.mjs` | 対象・保存待ち・確定待ち・古い応答・別Notebookの状態遷移 |
| `tests/unit/sidebar-presenter.test.mjs` | NodeForm公開APIと通知口の境界検査。実CSP・実OSを代替しない |
| `tests/manual/TASK-001-sidebar.md` | VS Codeでの対象表示、下書き復元、テーマ・キーボード・幅、標準Notebook共存の実機手順 |

Host provider、正式な共通schema・型、製品manifest・packagingの具体的ファイルは、それぞれの担当成果で指定する。UI側に仮の正式名・複製schemaを作らない。

## 実装単位と期待する検査

### Task 1: 対象と保存・確定状態を分離する

**Files:** 上記state.mjsとsidebar-state.test.mjsの候補。G1・G2・runner確定後に具体的な内部関数と型をこの節へ固定する。

**Interfaces:** 正式Host状態の表示モデルへの変換は境界アダプターの責務。UI内部は「対象」「所属Notebook」「編集可否」「下書き有無」「保存／確定待ち」「未更新」「失敗表示」を区別し、wire名やmetadataキーは保持しない。

- [ ] G1の承認済み例を読んで、対象A/B・同名Notebook・処理変更・削除→Undoの入力と期待状態をテストケースへ対応付ける。
- [ ] 下書き保存が失敗したときに対象Aと編集値が残り、Bへ成功したように移らないテストを先に作る。
- [ ] サイドバーフォーカス移動では対象維持、別Notebookでは編集不可、旧応答は新対象へ不適用、確定待ちは二重送信なしのケースを作る。
- [ ] 確定したrunnerで失敗を確認し、最小の純粋状態処理を実装して同じケースの成功を確認する。
- [ ] 対象commit・コマンド・結果を記録してコミットする。UI状態試験をNotebookの保存・識別の合格にしない。

### Task 2: NodeFormとサイドバー表示を接続する

**Files:** presenter.mjs、styles.css、sidebar-presenter.test.mjsの候補。Task 1と、承認済みのフォーム定義・取込経路を受けてから実装する。

**Interfaces:** Task 1のUI状態とNodeFormのmount／getParams／validate／destroyを使用する。送受信はG1の正式アダプターへ接続し、Python生成・metadata更新・OS選択はHostへ委ねる。

- [ ] A→B→Aの再描画で各値が復元し、再mountが入力通知やアクション変更にならないことを検査する。
- [ ] 検証NG時に該当項目へエラーを出し、commit通知が送られず、下書きと確定済み表示が混ざらないことを検査する。
- [ ] commit成功前の成功表示禁止、失敗時の値保持、古いbrowse応答の不適用、同名Notebookの識別表示を検査する。
- [ ] 固定上流・patch・CSS・許諾の来歴を保ち、正式な生成経路だけで評価済み部品を接続する。distを直接編集しない。
- [ ] テーマ変数・CSPに必要なマークアップとリソース参照を作り、確定runnerによる検査と差分確認後にコミットする。

### Task 3: Hostの標準WebviewViewへ統合して実機確認する

**Files:** UIの手動手順と、TASK-002／006が正本として確定した統合部分。正式な登録・起動・テスト入口を受領するまでファイル名やコマンドを埋めない。

**Interfaces:** G1の正式契約とG3のHost APIをそのまま利用する。セルの「設定」操作は指定セルを対象にし、Notebook sourceは確定するまで変更しない。

- [ ] 単一Viewの再利用、通常Python／初期化セルの非対象、セル移動・複製・削除・Undo、最後のタブ終了とNotebookDocument寿命をHost側の境界試験と照合する。
- [ ] draft通知・確定・同時編集・失敗・古い応答を、正式契約と実セルmetadata／sourceの結果まで確認する。単体アダプターの成功を実セル編集の成功にしない。
- [ ] 保存・再オープン、非表示・再表示、別Notebook・同名Notebook、フォーカス移動の手動ケースを作る。
- [ ] 標準のセル実行・Run All・例外・出力消去との共存、Light／Dark／High Contrast、狭い幅、キーボード・項目直下エラーをVS Codeで確認する。
- [ ] 操作案内はセル全体の選択とコード内カーソルを区別し、1回の操作と期待画面を示す。必要な実機操作は利用者、ログ整理はエージェントという既存の分担を使う。
- [ ] 未実施・不合格を区別し、不具合があれば担当Taskの許可範囲で修正・関連再確認する。出荷や親Taskの完了は独立に判定する。

## 最新のHost調査から引き継ぐ制約

[TASK-002-01](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/14)の2026-10-23のコメントでは、実環境はVS Code1.143.0、既存基準は1.142.0。版の差を記録し、製品の最低版とはしない。

[診断準備報告](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/14#issuecomment-6345093129)で、最後のタブを閉じてもNotebookDocumentのcloseが直ちに観測されない条件が報告されている。UIの「Notebookを閉じた」と、APIオブジェクト寿命・要求の有効期限を同一視しない。

D1はセル移動の部分観測があるが、D1全体・D2〜D6・製品の競合方式は未完了。別Taskの診断を再実行せず、担当Issueの確定した結果をG1／G3へ渡す。自分のUI試験で不足する実機根拠を代替しない。

## 計画を実行可能版へ進める条件

- [ ] G1／G2の作業範囲について利用者の判断を得て、担当Taskに正本・変更対象・完了条件を明示する。
- [ ] G1／G2／G3の対象部分を受領し、上の候補ファイル・正式な境界シグネチャ・実行コマンド・期待結果を固定する。
- [ ] 各UI要件とReview Focusをテスト名／手動ケースへ対応付け、自己レビューする。
- [ ] 実行可能な計画を利用者に提示し、実行方法を確認してから実装へ進む。同じUI動作の承認は繰り返し求めない。

今回はこの文書と承認記録・Issueの更新まで。Task実行記録のMarkdownは新規作成せず、進捗・結果はIssueで管理する。規約・契約・製品ソース・依存導入・ビルド・GUI操作は実施していない。
