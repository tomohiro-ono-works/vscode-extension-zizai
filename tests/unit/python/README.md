# Pythonパッケージの独立確認

対象は003-03の最小パッケージと003-04の先行確認です。コネクタの業務処理やJupyterの実機確認ではありません。

## 必要な環境と実行

- 確認用Python：3.12以降。標準unittest／venvを使用します。
- 確認用環境にsetuptools（pyprojectの要件を満たす版）とpip 22.3以降が必要です。
- 外部通信、pytest、SDK、認証情報は不要です。テストはビルド依存を自動導入しません。

リポジトリ直下で実行します。

```sh
python -m unittest discover -s tests/unit/python -p 'test_*.py' -v
```

別のPythonを実行先にする場合は、`ZIZAI_TEST_PYTHON`へその実行ファイルを指定します。POSIXの例：

```sh
ZIZAI_TEST_PYTHON=/usr/bin/python3.13 python -m unittest discover -s tests/unit/python -p 'test_*.py' -v
```

backendとpipを実行するのはコマンド先頭のPythonで、隔離venvを作成してimportするのは`ZIZAI_TEST_PYTHON`です。指定を省略すると両方が同じPythonになります。

## 判定する境界

| テスト | 判定すること |
| --- | --- |
| wheel収録 | coreとconnectorsの3 package入口が1つのwheelへ入り、無関係の別領域・作業データを含まない |
| 手動導入 | 未導入時のModuleNotFoundErrorと導入後の通常importを、同じ使い捨てvenv・別cwd・`-I`で比較。読込先とdistribution名も照合 |
| SDK非読込 | rootとpackage入口のimportにpandas・NumPy・Excel・DuckDB・Google SDKや個別コネクタを要求しない |
| 状態保持 | import前後でcwd・環境変数・sys.pathが変わらない |
| sdist経由 | ソース配布物を展開して再ビルドしたwheelでも収録・手動導入・importが成立する |
| Notebook診断 | 出力なし・標準kernelのNotebookについて、診断JSONが配布物と一致し、ローカルpathを出さない。同名sourceによる隠蔽を検出し、同一セッションと新規プロセスを区別する |

一時領域へソースをコピーし、setuptoolsの実backendを呼び、pipの`--no-index --no-deps`で生成済みwheelだけを導入します。pipのユーザー設定・環境変数を無視し、既存環境へインストールしません。一時領域は終了時に削除します。

003-02のU01〜U05の対象部分を確認します。個別SDK欠落時の処理、共通関数・戻り値、実際のwheel更新とカーネル再起動、正式な契約資産の読込は対象実装が成立してから確認します。現在の最小入口の合格で、これらを合格にしません。

[正本と配布経路](../../../apps/core/README.md)・[設計と確認ケース](../../../docs/research/python-import/TASK-003-02.md)を参照してください。

003-05の[実機手順とNotebook](../../manual/TASK-003-05-python.md)を用意しています。Notebookの診断コードも通常Pythonプロセスと実wheelで確認しますが、ipykernelを起動した結果や、VS Code上のカーネル再起動の合格には数えません。現在は配布5件＋Notebook診断4件の合計9件です。テスト専用のpackage生成・導入処理は`package_test_support.py`へ集約し、製品packageへは収録しません。
