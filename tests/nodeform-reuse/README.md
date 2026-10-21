# TASK-001-02 NodeForm単体評価

評価用であり、製品実装やNotebook内のHTMLフォーム常設試作ではない。上流コードを変更せず、独立したChromiumページでAPI・DOMイベント・破棄動作を調べる。OSダイアログは開かず、ファイル選択結果はDOMイベントで模擬する。

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

スクリプトは上流4ファイルのGit blob hashを照合してから実行する。検査対象ファイルが違う版／改変版なら停止する。ブラウザのローカルファイルURL制限に依存しないよう、取得済みJSとサンプルHTMLを空ページへ注入する。サンプルHTMLの外部scriptタグ2個をメモリ上で省き、同じ取得済みJSを先に読み込む。上流ファイル自体は変更しない。この方法では実URL読み込みやCSP適合を検証できない。

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

既知の不合格を隠さず、スクリプト全体の終了コードは **1**。イベント計測は検証ページのdocument.addEventListener／removeEventListenerを包んでpointerdownの登録数を数える。上流本体には計測コードを加えていない。

別の暗色親要素を持つページで上流CSSを読み込み、前景 `rgb(238, 238, 238)` に対して背景 `rgb(255, 255, 255)` を観測した。これは固定白背景の確認であり、VS Codeテーマ試験の結果ではない。

## 評価の境界

- ブラウザ単体のAPI・DOM検査であり、Renderer／Webview／Notebook source・metadata・Python実行を扱わない。
- 部品APIの候補適性と、comboのリスナー修正・テーマ調整が必要なことを判断するための材料。
- 上流の修正、製品へのvendor配置、正式な共通契約、サイドパネル等への配置変更は行っていない。
