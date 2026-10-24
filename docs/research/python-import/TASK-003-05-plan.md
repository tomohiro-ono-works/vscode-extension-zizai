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
