# 対象IDEと初回配布方式の判断

判断日：2026-10-22。関連：[TASK-006](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/6)、[TASK-006-01](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/41)、[PR #49](https://github.com/tomohiro-ono-works/vscode-extension-zizai/pull/49)。

## 配布の基本方式

利用者の「OKです。であれば、一旦、wheelとvsix案でOKです」を根拠に、VSIX＋自作Python wheelを初回配布の基本方式として採用する。両者を1つのZIPに同梱し、任意展開・手動導入・既存Jupyterカーネル・個別版管理という全体設計を維持する。

既存のNotebook実行環境を前提に、利用者の追加導入を拡張VSIXとPythonライブラリ・必要なPython依存に収める。専用exeインストーラー、別途のNode.js／npm／ビルドツール、独自サーバーの導入を利用者に求めない。

## 正式対象の変更

利用者の指示：

> VSCodeのみを想定して、kiroはVSCodeベースだから、つかえたらいいね。　くらいでOKです。

正式対象と必須の互換性・実機確認はVS Codeのみとする。Kiroは任意の互換利用の参考対象で、動作保証・専用対応・必須検証・出荷判定の条件には含めない。Kiroでの動作が確認済みであることや、VS Codeとの完全互換性を、この判断で認定しない。

この明示的な指示に基づき、[全体設計](../designs/01全体設計.md)、[UI設計](../designs/02NotebookUI設計.md)、[アーキテクチャ](../features/architecture.md)、README・開発案内と、関連Issueの両IDE必須条件を更新する。以前の調査範囲・結果・採用前の判断履歴は保持する。

## 継続する設計と境界

[環境・配布設計](../research/development/TASK-006-01.md)で、初回の検証基準候補、7コネクタの依存と外部ソフト条件、package・ビルド・導入の責務を具体化する。対応版、最低版、全推移依存、ライセンス同梱、UIの配置・起動条件は検証済みと区別する。

今回の変更・継続許可は設計・調査・文書とIssueへの反映を対象とする。製品コード・manifest・lock・起動設定の作成、環境設定変更、依存導入、ビルド・CI・パッケージ化・実機操作・公開の許可には広げない。通常のPythonとJupyter標準実行の方針、初回7コネクタの区分、セキュリティ境界は変更しない。
