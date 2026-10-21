# TASK-003-01 Python参照の補助確認（試作）

標準ライブラリだけで、外部一時フォルダーの架空パッケージを通常Pythonプロセスから読み込む。製品のPythonライブラリ、コネクタ、独自カーネル、実行サーバーではない。Jupyter／VS Codeは起動しない。

リポジトリ直下で実行する。

```sh
python tests/python-import-research/probe.py --report /path/to/import-result.json
```

Python 3.12.14／Linuxで8件合格。追加パッケージの導入、既存環境・kernelspecの変更は不要。子プロセスにだけPYTHONPATHを設定するケースがあり、親環境は変更しない。入力には空白と日本語を含む一時パスを使い、別の作業ディレクトリから実行する。一時フォルダーは終了時に削除する。

| ID | 確認 | 期待結果 |
| --- | --- | --- |
| I1 | 探索パスへ追加せずimport | ModuleNotFoundErrorで終了1 |
| I2 | 絶対パスをsys.pathへ追加し、別のcwdからimport | 展開先Aの値を返して終了0 |
| I3 | 起動前にPYTHONPATHへ展開先Aを追加 | Aの値を返して終了0 |
| I4 | 起動後にos.environのPYTHONPATHだけを変更 | ModuleNotFoundErrorで終了1 |
| I5 | Aをimport後、探索パスの先頭をBへ変更して再import | 同じモジュールオブジェクトのAを返す |
| I6 | 新規プロセスをBのPYTHONPATHで起動 | Bの値を返して終了0 |
| I7 | パッケージの依存モジュールが存在しない | 依存名のModuleNotFoundErrorで終了1 |
| I8 | 架空処理がValueErrorを送出 | 通常のValueErrorで終了1 |

失敗が期待されるケースも、終了コードと例外の種類・内容が一致した場合に補助確認の合格とする。スクリプト自体は全件一致で終了0、不一致があれば終了1。レポートにはfixture、コードのテンプレート、期待値・実測値、probeのhashを残す。認証情報や実データは入力しない。

[調査と残る条件](../../docs/research/python-import/TASK-003-01.md)、[実行JSON](../../docs/research/python-import/evidence/TASK-003-01-python.json) を参照。Python 3.12.13・Windows・既存Jupyterカーネルでの確認ではなく、再起動やNotebook間の共有・分離も実証していない。実際の配布物のpip導入・依存解決は未実施。
