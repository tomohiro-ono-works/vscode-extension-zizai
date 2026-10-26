# Pythonパッケージの独立確認

対象は003-03の最小パッケージと003-04の先行確認です。コネクタの業務処理やJupyterの実機確認ではありません。

## 操作経路による分類と担当

[開発手順](../../../docs/development.md)に従い、起動にunittestやCLIを使うことと検証分類を分けます。下表9件はエージェントが準備・実行・証跡採取・分析・記録を担当し、ユーザーへターミナル操作やログ整理を依頼しません。

| テストメソッド | 分類 | 実際の操作・検証経路 |
| --- | --- | --- |
| `test_notebook_is_unexecuted_and_uses_a_standard_kernel` | 単体 | Notebook JSONの未実行状態・metadata・セル構文を直接検査 |
| `test_wheel_contains_both_source_roots_without_unrelated_assets` | API・結合 | build backendを呼び、生成wheelの収録内容を検査 |
| `test_hand_installation_enables_imports_without_source_paths` | API・結合 | 別プロセス・使い捨てvenv・pip導入とimportの前後を照合 |
| `test_package_imports_do_not_require_optional_sdks` | API・結合 | 実wheelを導入し、別Pythonで不要SDKの読込要求を検査 |
| `test_import_preserves_cwd_environment_and_search_path` | API・結合 | 実wheelを導入し、別Pythonでimport前後の状態を照合 |
| `test_sdist_rebuild_preserves_split_package_imports` | API・結合 | backendでsdist・wheelを作成し、新規venvへ導入してimport |
| `test_diagnostic_matches_the_wheel_without_exposing_local_paths` | API・結合 | Notebookの診断コードを通常Pythonで評価し、実wheelとJSONを照合 |
| `test_restart_check_distinguishes_current_and_fresh_processes` | API・結合 | 通常Pythonの同一／新規プロセスでセッション判定を比較 |
| `test_diagnostic_detects_packages_shadowed_by_notebook_cwd` | API・結合 | 別cwdの同名packageを通常Pythonで読み込み、診断を照合 |

各ケースの目的・期待結果は下の境界表とテスト内のassertionを正本とします。対象は実行時のcheckout・build backend・Python版を記録し、開始条件は次節の依存確認と対象ソースの存在です。証跡には各メソッドの結果、対象版・環境・コマンド、変更条件と観測限界を残します。

UI自動テスト・手動UI検証はこの9件に含みません。診断コードの通常Python実行や新規プロセスの成功は、VS Codeでのセル操作・カーネル再起動・表示の手動UI合格を示しません。UI自動テストを追加する場合はPlaywrightの範囲・開始方法・担当を事前合意します。

## 必要な環境と実行

- 確認用Python：3.12以降。標準unittest／venvを使用します。
- コマンド先頭のPythonから、`-I`付きでもsetuptools（pyprojectの要件を満たす版）とpip 22.3以降を読み込める環境が必要です。
- 外部通信、pytest、SDK、認証情報は不要です。テストはビルド依存を自動導入しません。

実行前に、テストを起動するPythonでビルド依存を確認します。

```sh
python -I -c "from setuptools import build_meta; import pip; import importlib.metadata as m; print({p: m.version(p) for p in ('setuptools', 'pip')})"
```

ユーザー領域だけに導入したsetuptoolsは、通常起動で利用できても`-I`では見えません。この場合はテスト専用venvへ必要な版を明示的に用意し、そのvenvのPythonで上記確認と次のテストコマンドを実行します。venvの準備はテスト実行と分け、runnerの隔離オプションを外して成立させないでください。

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
