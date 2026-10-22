# TASK-001-02 NodeForm単体評価

評価用であり、製品実装やNotebook内のHTMLフォーム常設試作ではない。固定した上流コードと検証用パッチを分け、独立したChromiumページでAPI・DOMイベント・破棄動作を調べる。OSダイアログは開かず、ファイル選択結果はDOMイベントで模擬する。

取得元は [zizai-form](https://github.com/tomohiro-ono-works/zizai-form)、対象commitは `f08bfc73350d04e9238b43fa4dbcfdb81fa5150e`。[Zizai向け利用許諾](../../docs/decisions/nodeform-reuse-permission.md) を記録済み。上流のLICENSEは維持する。上流コードはこのリポジトリにvendorせず、外部の一時チェックアウトを使う。

## 再現

PythonとPlaywright、実行できるChromiumが必要。クラウドで確認した版はPython 3.12.14、Node 24.19.0、Playwright 1.62.0、Chromium 154.0.8037.57。ブラウザ単体の評価であり、WindowsのVS Code 1.142.0上の適合結果ではない。

リポジトリ直下で実行する。clone先は未使用の作業フォルダーを指定する。

```sh
git clone -c core.autocrlf=false https://github.com/tomohiro-ono-works/zizai-form.git ../zizai-form-check
git -C ../zizai-form-check checkout --detach f08bfc73350d04e9238b43fa4dbcfdb81fa5150e
node ../zizai-form-check/test/node-form.test.js
python tests/nodeform-reuse/browser-probe.py ../zizai-form-check --chromium /path/to/chromium --report /path/to/result.json
```

Playwrightが未導入の場合は、検証用Python環境へ `python -m pip install playwright` で導入する。システムのChromiumを指定しない場合は、Playwrightの `python -m playwright install chromium` でブラウザを準備する。この場合、`--chromium` に準備した実行ファイルを指定する。クラウドでは既存のPlaywrightと `/usr/bin/chromium` を使い、追加導入はしていない。

スクリプトは上流4ファイルのGit blob hashを照合してから実行する。検査対象ファイルが違う版／改変版なら停止する。ブラウザのローカルファイルURL制限に依存しないよう、取得済みJSとサンプルHTMLを空ページへ注入する。サンプルHTMLの外部scriptタグ2個をメモリ上で省き、同じ取得済みJSを先に読み込む。元のチェックアウト自体は変更しない。`--patched` では外部一時コピーにだけ同梱patchを適用し、上流の既存テストもそのコピーで再実行する。この方法では実URL読み込みやCSP適合を検証できない。

クラウドの標準sandboxではChromiumが `setsockopt: Operation not permitted` で起動できず、ネットワーク権限を追加したコマンド実行では起動した。file://表示は `ERR_BLOCKED_BY_ADMINISTRATOR` となったため、上記のページ注入方式で評価した。独立ページへの表示はIDE・Webviewの合格にはしない。

## 期待結果と実施結果

[実行JSON](../../docs/research/notebook-ui/evidence/TASK-001-02-browser.json) を参照。上流の既存テストは `node-form tests passed` で終了した。

| 検査 | 結果 |
| --- | --- |
| 値の設定・取得、必須検証、復元時は通知せず元データを変更しない | 合格 |
| ユーザー入力通知と複数フォームの値の分離 | 合格 |
| visible_ifによる表示と検証切替、非表示値の保持 | 合格 |
| 模擬ファイル選択結果・キャンセル | 合格（実OS選択は対象外） |
| 破棄時のDOM削除と遅延したbrowse結果の無視 | 合格 |
| comboへ3回入力し、破棄後にdocumentのpointerdownリスナーが残らない | **不合格：2件残る** |

既知の不合格を隠さず、未修正版でのスクリプト全体の終了コードは **1**。イベント計測は検証ページのdocument.addEventListener／removeEventListenerを包んでpointerdownの登録数を数える。上流本体には計測コードを加えていない。

別の暗色親要素を持つページで上流CSSを読み込み、前景 `rgb(238, 238, 238)` に対して背景 `rgb(255, 255, 255)` を観測した。これは固定白背景の確認であり、VS Codeテーマ試験の結果ではない。

## 評価の境界

- ブラウザ単体のAPI・DOM検査であり、Renderer／Webview／Notebook source・metadata・Python実行を扱わない。
- 部品APIの候補適性と、comboのリスナー修正・テーマ調整が必要なことを判断するための材料。
- 上流リポジトリへの修正送信、製品へのvendor配置、正式な共通契約、サイドパネル等への配置変更は行っていない。

## 検証用の修正と配色調整

利用者の「進めて下さい」により、TASK-001-02の評価範囲で再現不具合の修正と配色調整を実施した。上流リポジトリや製品コードは変更していない。

- `patches/0001-combo-listener.patch` は、comboのメニューを再表示する直前に前のoutsideリスナーを解除する1行の追加。元commitへ `git apply --check` を通し、元チェックアウトを一時コピーしてから適用する。
- `vscode-theme-probe.css` は検証専用の上書きCSS。node-form内に限定して入力・ボタン・候補メニュー・エラー・フォーカス・枠線へVS CodeのCSS変数を使う。上流CSSは編集しない。
- ブラウザの配色検査は、Light／Dark／High Contrastを模した変数値を注入し、入力・textarea・select・ボタン・メニューの色、枠線、エラー、フォーカスとフォーム外への非干渉を比較する。実際のVS CodeテーマやHigh Contrastの実機試験とは区別する。

```sh
python tests/nodeform-reuse/browser-probe.py ../zizai-form-check --chromium /path/to/chromium --patched --theme-checks --theme-override tests/nodeform-reuse/vscode-theme-probe.css --report /path/to/patched-result.json
```

[修正後のJSON](../../docs/research/notebook-ui/evidence/TASK-001-02-patched-browser.json) は上流テスト合格、ブラウザ単体6件・配色3条件すべて合格、終了コード0。comboの破棄後のdocument.pointerdownは2件から0件へ減った。patchと上書きCSSのSHA-256もレポートへ記録する。

比較用に、[配色調整前のJSON](../../docs/research/notebook-ui/evidence/TASK-001-02-theme-before.json) はパッチ適用済みの単体6件が合格、CSS未調整の配色3条件が不合格で終了コード1。最初の未修正版の不合格記録も書き換えない。修正後JSONのbaseCssDarkParentは上流CSSだけの観測を保持し、上書き後の値はthemeChecksで確認する。

取り込み時は上流commit・patch・上書きCSS・利用許諾をセットで追跡する。これらはTASK-001-02の評価物で、Notebook内フォームの配置や正式なvendor方式を決めるものではない。

## VS Codeでの評価用Webview

[実機手順F1〜F6](../manual/TASK-001-02-nodeform.md) を追加した。検証拡張0.0.1、拡張IDは `zizai-lab.task-001-02-nodeform-probe`。F5の **TASK-001-02: NodeForm Reuse (PROTOTYPE)** で起動する。これは部品のIDE適合を確認するための一時的なタブであり、製品のフォーム配置を採用したものではない。

`prepare-webview.mjs` は固定commitの3ファイルを取得またはローカルから読み、Git blob hashを照合する。dist/upstream/へ元ファイルをキャッシュし、外部一時コピーでpatchを適用してからdist/webview/を生成する。生成したmanifestにRendererや提案APIは含めず、上流LICENSEと本プロジェクト向けの許諾記録を保持する。生成物へ直接patchしない。

```sh
node tests/nodeform-reuse/prepare-webview.mjs ../zizai-form-check
node tests/nodeform-reuse/webview-host.test.cjs
```

クラウドではローカル固定commitからの生成、キャッシュなしの初回取得、キャッシュ再利用、破損キャッシュの拒否を確認済み。F5での実起動とWindowsでの初回取得は未実施。Nodeの子プロセス起動に制限があるsandboxでは生成に権限付き実行が必要だった。

### patchの改行と回帰テスト

Windowsから、準備中の `git apply --check` が `src/node-form.js:197` で失敗した報告を受けた。ローカルの調査結果は `i/lf w/crlf`、`core.autocrlf=true`。固定上流はLFのままなので、patchだけがCRLFへ変換されるとクラウドでも同じ失敗を再現する。

`prepare-webview.mjs` と `browser-probe.py --patched` は、patchのCRLFをメモリ上でLFに揃え、標準入力から `git apply --check -`／`git apply -` へ渡す。元のpatch・上流ファイル・Git設定は変更しない。上流のblob hash照合も維持するため、上流ファイル自体を改行変換した場合は引き続き拒否する。

一時コピーから親のGitリポジトリを探索しないよう、Git子プロセスの `GIT_CEILING_DIRECTORIES` を一時コピーの親ディレクトリへ指定する。さらにそのコマンド内だけ `-c core.autocrlf=false -c core.eol=lf` を指定し、グローバル設定による生成JSのCRLF変換も防ぐ。ユーザーの設定ファイルには書き込まない。

`provenance.json` とブラウザ報告の `patchSha256` は元のpatchファイル、追加した `appliedPatchSha256` は実際に適用したLFの内容を表す。patchの改行だけが違う場合、前者は異なり、後者と生成したフォーム資源は一致する。

```sh
node tests/nodeform-reuse/prepare-webview.mjs
node --test tests/nodeform-reuse/prepare-webview.test.mjs
```

最初のコマンドで固定上流3ファイルをキャッシュする。回帰テストはそのキャッシュを一時領域へコピーし、fetchを拒否して実際のGitで検査する。LF／CRLF、祖先Gitリポジトリとローカル／グローバルautocrlf、修正行の実適用、生成物・来歴の一致、改変／改行変換した上流の拒否、不正patchの拒否と既存生成物保持を確認する7件。利用者のGit設定や既存キャッシュを変更しない。

2026-10-22、修正前は7件中4件合格・CRLF関連3件失敗、修正後は7件合格。[結果と対象版](../../docs/research/notebook-ui/evidence/TASK-001-02-patch-line-endings.json) を参照。Python側も修正前のCRLF失敗を再現し、修正後はLF／CRLFそれぞれ上流テスト・機能6件・配色3条件が合格した。Windowsで修正版を準備・起動した結果は未確認。

### キャッシュなしの初回セットアップ確認

2026-10-21、開始版 `563403c` の検証ソースと許諾文書を、同じ相対配置の一時領域へコピーした。dist/をコピーせず、既存の作業環境のキャッシュ・生成物を変更せずに確認した。[実行結果とファイルhash](../../docs/research/notebook-ui/evidence/TASK-001-02-setup.json) を参照。

| ケース | 実際の結果 |
| --- | --- |
| P0：空キャッシュで引数なし実行 | クラウドでは `fetch failed`／`EAI_AGAIN raw.githubusercontent.com`、終了1。継承したプロキシを使わないNodeの取得経路で失敗 |
| P1：Nodeの環境プロキシ利用を有効化して初回実行 | 終了0。JS／CSS／LICENSEの3ファイルが固定blob hashと一致。patch、テーマCSS、許諾、manifestを含む生成9ファイルを検査 |
| P2：P1のキャッシュを使い、fetchを明示的に拒否して再生成 | 終了0、fetch呼出0回。生成9ファイルのhashはP1と一致 |
| P3：一時コピーのキャッシュJS末尾へコメントを追加して実行 | 期待通り終了1、`pinned upstream blob mismatch`。fetch呼出0回、既存生成物は変更されない。検査後に一時キャッシュを元へ戻した |

初回取得の再現は、dist/が存在しない検証用コピーのルートで次を実行する。JS／CSS／LICENSEを固定commitから取得するので、ネットワーク上で `raw.githubusercontent.com` に到達できる必要がある。

```sh
node tests/nodeform-reuse/prepare-webview.mjs
```

このクラウドのNode 24.19.0では、上記は直接接続のDNS解決で失敗し、既存のプロキシ・CA設定を保持した次の実行で成功した。

```sh
node --use-env-proxy tests/nodeform-reuse/prepare-webview.mjs
```

`--use-env-proxy` は今回のNode 24で確認した環境条件。Node 20を含む全対応版で使えるオプションとは扱わず、共通のF5設定へ追加しない。Windowsでこのオプションが必要とは判断していない。プロキシ経由で取得できない環境では、上記の固定commitのローカル取得元を指定する手順を使う。

P2／P3では、報告JSONの `fetchGuardSource` を `deny-fetch.mjs` として検証用コピーのルートに置き、`node --import ./deny-fetch.mjs tests/nodeform-reuse/prepare-webview.mjs` で実行した。P3は一時キャッシュだけを変更する。通常の準備コマンドでは改変キャッシュを自動的に上書きしないので、意図しない版を使って検証を続行することはない。

### Hostテストの境界

`webview-host.test.cjs` はVS Code APIアダプターで、キャンセル・不正要求・閉じたパネルへの遅延結果・並行要求・環境情報・CSP宣言を検査する4件。最初は並行要求のケースが失敗し、保留せずキャンセル結果を返す修正後に4件合格。実際のCSP適用・OSダイアログ・Webview描画はこのテストの対象外。

仮のDOM／Hostメッセージはこの検証拡張内だけのもの。選択パスはフォームへ返すだけで内容を読まず、PythonやNotebookを操作しない。OutputChannelは作らない。実機結果が返るまでは、TaskのIDE適合は未実施のまま保持する。

### Webview再表示時の入力保持

評価用クライアントはVS CodeのWebview単位の `getState`／`setState` でフォーム値を保存し、タブを非表示にして文書が再作成された場合も復元する。「フォームを作り直す」はそのパネルのフォームと保存値だけを初期化する。候補・条件付き項目・ファイル／フォルダーの選択パスもフォーム値として保持するが、内容の読み込み、環境報告JSONへの追加、OutputChannelへの出力は行わない。この状態保持は評価用タブだけの処理であり、製品の保存契約を定義しない。

次のコマンドで準備7件・Host4件・クライアント3件をまとめて確認する。Windowsの回帰テストでは `--import` の取得拒否ガードをfile URLとして渡す。

```sh
node --test tests/nodeform-reuse/prepare-webview.test.mjs tests/nodeform-reuse/webview-host.test.cjs tests/nodeform-reuse/webview-client.test.cjs
```

`webview-client.test.cjs` は実クライアントスクリプトを別々のJS文書として起動し、値の復元、再作成後の初期化、パネル間の分離を検査する。VS Code APIとNodeFormの公開APIはアダプターで置き換えており、実WebviewでのF6合格を示すものではない。生成後にF5で起動し、[実機手順F6](../manual/TASK-001-02-nodeform.md) の同じエディターグループ内でのタブ往復と、一方だけのフォーム再作成を確認する。
