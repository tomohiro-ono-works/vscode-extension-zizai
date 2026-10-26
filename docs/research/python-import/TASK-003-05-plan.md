# TASK-003-05 最小基盤のカーネル確認準備

対象は003のPython共通基盤。最小packageが実装された範囲で、VS Codeの選択済み既存カーネルから通常import・再初期化を確認する手順を用意する。個別コネクタ・契約資産・他Taskの配布設定は変更しない。

入力：[003-02の設計](TASK-003-02.md)、[003-03の最小実装](TASK-003-03-plan.md)、[PR #54](https://github.com/tomohiro-ono-works/vscode-extension-zizai/pull/54)の`4dcadc2decf7563ec8f75f25f003479762daf9d3`。

## 作成対象と期待結果

| 対象 | 役割 |
| --- | --- |
| `tests/manual/TASK-003-05-python.ipynb` | 通常Pythonセルによる環境のローカル確認、3 packageのimport、再起動前後の診断JSON |
| `tests/manual/TASK-003-05-python.md` | 手動導入、実行順序、未導入時の標準例外、期待結果と残るケース |
| `tests/unit/python/package_test_support.py` | 既存のwheel生成・隔離venv操作をテスト内で共有。製品の実行基盤には含めない |
| `tests/unit/python/test_notebook_handoff.py` | Notebookの未実行状態・診断の出所判定・パス非公開・再起動確認ロジックを実配布物で独立確認 |
| 既存のPythonテスト／README | 共有fixtureの参照とNotebook確認の案内 |

## 手順

1. 既存5テストのfixtureをテスト専用moduleへ移し、5件が継続合格することを確認する。
2. Notebook未作成で新規4テストが失敗することを確認する。
3. 標準python3 kernelspec・出力なしのNotebookと手動手順を作る。pip・環境変更・実行制御をNotebookへ追加しない。
4. 診断はmetadataと実moduleの出所一致、ファイルhash、import前後のcwd／環境／sys.pathの保持を記録する。共有JSONには絶対pathや環境変数を含めない。
5. 再起動後は標準操作で必要なセルだけを実行する。同一セッションと新しいPythonプロセスの区別を自動確認するが、これを実際のJupyter再起動の合格にしない。
6. 2つの確認済みPython実行先で全独立テストを実行し、文書・Notebookの参照・出力非保存を照合する。
7. 003のIssueとPRへ結果と未実施を記録する。

## 確認の境界

クラウドでは通常Pythonプロセスで診断コードを確認する。ipykernelやIDEの追加導入、既存kernelspecの変更は行わない。VS Code／Windows／候補Python3.14の実機、製品のインスタンス生成・呼出し、個別SDK欠落、実際の更新と再起動は未実施として残す。現在の製品に存在しないAPIやダミーコネクタは作らない。

## 今後の検証方法と実施順

共通ルール`5bbb234`／`fa21803`を適用する。依存関係の区分・必要成果・工程・充足根拠は[#21](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/21)〜[#24](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/24)の現在欄を正本とし、相手Task全体の完了を必要条件へ広げない。Python向け契約資産の要否・生成先・利用経路が未確定なら、その収録実装だけを保留し、最小packageの確認は独立して進める。

1. エージェントが、前提の揃った既存9件を現在のcheckoutで確認する。内訳は単体1件とAPI・結合8件で、[ケース別の操作経路](../../../tests/unit/python/README.md)に従う。build・pip・通常Python subprocessを使い、GUIは操作しない。
2. エージェントが、出力なしNotebookの作業コピー・wheelの出所・既存Python環境・保存先と診断JSONの採取方法を確認する。通常Pythonからのimport事前確認はAPI・結合であり、手動UIとは分ける。
3. [手動UI手順](../../../tests/manual/TASK-003-05-python.md)の準備完了を報告し、ユーザーの開始合図を待つ。開始合図後に専用ウィンドウを用意し、K01から小さく案内する。ユーザーがセル操作・再起動・表示確認を行い、エージェントが準備・採取・分析・記録を担当する。
4. UI自動テストは未計画。必要な場合はPlaywrightの対象範囲・開始方法・担当を事前合意し、対応不能を理由に別の自動操作へ切り替えない。

過去のエージェントGUI自動操作によるK01〜K04の証跡は履歴として残す。新ルールのユーザー手動UI合格へ振り替えず、実際の操作担当・経路と未実施の手動UI確認をIssueに併記する。API・自動テストの成功、アプリ起動成功、通常Pythonのセッション判定だけで手動UIの成功とはしない。
