<a id="architecture"></a>
# アーキテクチャ

日本語化日: 2026-10-04。記載内容・承認状態は変更せず、従来の見出しへの参照を維持。

- Status: Current Specification
- Last verified: 2026-09-15
- 決定記録: [ADR-v23 アプリケーション構成](../decisions/ADR-v23-application-topology.md)、[ADR ソース・実行環境・ワークスペースの境界](../decisions/ADR-source-runtime-workspace-boundary.md)、[ADR Web許可リストの正規化](../decisions/ADR-web-allowlist-canonicalization.md)

<a id="runtime-topology"></a>
## 実行時の構成

現行Applicationは、Windowsローカルで動く単一Desktop Runtimeである。PySide6/QtWebEngineが同梱HTMLを`file://`で読み込み、FrontendとPythonはQWebChannel Bridgeで通信する。

- 承認target: 同じGUI Python processのFastAPI／Uvicorn loopback HTTP＋SSEと、通常Chrome／Edge tabへの同梱Frontend配信。独立deploy service／LAN公開なし。
- 詳細の単一正本: [Browser Runtime](browser-runtime.md)。採用理由・ADR-v23の部分置換は[後継ADR](../decisions/ADR-localhost-browser-runtime-migration.md)。
- 現行source／標準起動はWebViewのまま。P1 prototype default OFF、P6切替承認、P7 Qt削除を別Gateとし、仕様採用を実装済みと扱わない。
- 内蔵WebViewは同梱Frontend専用とし、外部Pageや外部配信JavaScriptをBridge到達可能なContextへ入れない。
- 外部URLはAllowlistで検証し、許可時だけOS browserへ委譲する。
- 同梱`dataflow.html`の内部frame contractはApplication Bridge contractと分離する。現行WebView境界は切替まで維持。Browser targetのstatic root／CSP／Origin・client認可は[詳細仕様](browser-runtime.md#security)を正とする。

<a id="web-allowlist-boundary"></a>
## Web許可リストの境界

- allowlist entryはURL全体ではなくdomain／hostを表す。http／https URLで入力された場合はhostだけを抽出し、scheme、path、query、fragmentを保存しない。
- hostはlowercase、末尾のslash／DNS root dot除去、IDNからASCII punycodeへの変換を行ってCanonical形式にする。明示port、userinfo、`localhost`、単一label host、IPv4、IPv6、不正なDNS labelは受理しない。
- `example.com`はexact hostだけに一致し、subdomainへ許可を広げない。`*.example.com`はexactに1階層下のsubdomainだけに一致し、apexと多階層subdomainには一致しない。
- target URLのschemeはhttp／httpsだけを受理する。portは現行どおりallowlistの判定要素に含めず、port単位の許可は提供しない。pathの許可範囲は既存の`path_prefixes`で判定する。
- Canonical domainが重複するentryは統合し、`path_prefixes`を重複排除する。不正entryはそのentryだけを除外してwarningと非機密な件数statusを残し、正常entryの判定は維持する。
- `path_prefixes`を省略したentryは既定で`/`を許可する。`path_prefixes`を明示した場合にlistでない、空list、null、非文字列要素、空文字列要素のいずれかに該当するentryは、`["/"]`へfallbackさせずentry全体を除外する。

<a id="current-responsibility-map"></a>
## 現在の責務一覧

| Path | Responsibility |
|---|---|
| `zizai.py` | 正式入口。GUI、`--debug`、`.zizd` headless実行を振り分ける |
| `bin/ziz.bat` | Windows launcher。引数を`zizai.py`へ透過する |
| `apps/cli/main.py` | `run_cli()`によるheadless実行入口 |
| `apps/desktop/host.py` | PySide6、QtWebEngine、QWebChannel、ローカルの画面遷移境界 |
| `apps/desktop/bridge.py` | Frontend向けApplication InterfaceとBridgeRuntime |
| `apps/core/` | Workflow実行、flow path、型、logging等のApplication logicとConnector Interface |
| `apps/connectors/` | 外部System、file format、OS操作のAdapter |
| `apps/common/contracts/bridge/` | 言語中立なBridge Protocol contract |
| `apps/gui/` | Desktop同梱Frontend |
| `config/` | local Runtime/User state。Source設定は`apps/common/config/`に置き、両者を同一扱いしない |

<a id="dependency-boundaries"></a>
## 依存関係の境界

- Desktop/CLIはCoreを利用する。承認Browser targetではGUI／CLI共通Application ServicesをCore、HTTP／sessionとProtocol façade・nativeをDesktop Adapterが所有。CLIはHTTP非経由。Qtは移行中の旧WebView経路へ隔離し、独立apps/apiは作成しない。
- ConnectorはCoreが定義する実行・型contractに従う。
- CoreへQt、Frontend、具体Connectorの責務を混在させない。
- FrontendはPython実装を直接参照せず、Bridge contractを通じて通信する。
- 共有領域にはConfig、型、言語中立Contractだけを置き、Business Logicを置かない。
- Pathやpackageの物理移動は、launcher、dynamic discovery、config、asset、test、CI、active documentationの参照更新と同時に行う。

<a id="stable-contracts-during-migration"></a>
## 移行中に維持する契約

- 正式CLI互換対象は`bin/ziz.bat`と`zizai.py`である。
- Flow extensionは`.zizd`である。
- Bridge Protocol `1.0`の`cmd`/`res`/`evt` envelope、31 Command、8 Event、error形式をMigration完了まで維持する。
- Connector入口は`execute(action, params, context)`を維持する。
- Breaking changeはRepository移行へ混在させず、専用DecisionとTaskを必要とする。

<a id="approved-target-responsibilities"></a>
## 承認済みの目標責務

Target Treeは`apps/{desktop,cli,gui,core,connectors,common}`である。Python責務は`apps/{desktop,cli,core,connectors}`、Frontendは`apps/gui/`へ移行済みである。詳細と依存方向はADRを正とする。Browser targetのRuntime／責務は[後継ADR](../decisions/ADR-localhost-browser-runtime-migration.md)と[Runtime仕様](browser-runtime.md#runtime-topology)へ採用済みであり、sourceへの実装は未実施。

<a id="approved-configuration-boundary"></a>
## 承認済みの設定境界

- Source設定は`apps/common/config/`、Runtime/User stateは既存root `config/`、Workspace既定はroot `workflows/`へ分離する。
- Production entrypointが明示的なrepository rootを共通Path Resolverへ渡し、HTML位置やmodule階層から各rootを個別に逆算しない。
- Source設定はPython/Application Adapterが用途別に取得し、Source pathまたは汎用scopeをFrontend libraryへ渡さない。
- Runtime stateはRuntime専用scope、利用者が選択したWorkspaceはWorkspace専用scopeで扱う。Source設定とRuntime内部fileをExplorerの汎用操作対象にしない。
- Bridge Protocol `1.0`のCommand/Event数と既存payload fieldを維持し、追加payloadまたはscope値だけで境界を拡張する。
- 詳細な取得、cache、deprecated field、failure contractは`ADR-source-runtime-workspace-boundary.md`を正とする。

<a id="logging"></a>
## ログ記録

- `QueueHandler`/`QueueListener`による非同期loggingを使用する。
- `logs/app_YYYYMMDD.log`、1 file 10 MiB、同日backup 3、保持14日、総量1 GiBを上限とする。
- 通常levelは`INFO`、`ZIZ_LOG_LEVEL`で調査時だけ変更する。
- `logs/`はruntime artifactでありSource管理しない。
- Browser targetのHTTP／Application／console・計測は[秘密非露出Contract](browser-runtime.md#security)。既存save trace・request本文を新経路へ流用しない。
