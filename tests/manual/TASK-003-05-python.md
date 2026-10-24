# TASK-003-05 Python最小基盤の選択カーネル確認

対象は003の最小package。対応する[Notebook](TASK-003-05-python.ipynb)は通常Pythonセルだけで、VS Codeの標準Jupyter実行を使う。現在のpackageにはクラス・業務関数・SDK依存がまだなく、そのインスタンス生成・呼出し・依存欠落の確認は対象実装が揃ってから追加する。

## 前提と手動導入

1. この手順を含むPRのbranch／commitを取得する。対象版は実施結果に記録する。クラウドとデスクトップのファイルが自動同期されるとは扱わない。
2. VS Code、既存のPython／Jupyter拡張、確認用の既存Pythonカーネルを使う。独自カーネルやkernelspecは作成しない。初回の検証基準候補はWindows x64／通常ABIのPython3.14だが、実際に選択した版を取得して記録する。
3. Notebookを一時作業folderへコピーして開き、対象カーネルを選ぶ。セル1で実Pythonとcwdをローカル確認する。cwdはsource treeと別の場所にし、`zizai.py`や同名packageがそのfolderにないことを確認する。必要ならその一時folderをVS Codeで開き直す。Notebook保存先だけからcwdを推測しない。
4. setuptoolsがあるビルド用Python環境で、リポジトリ直下から開発wheelを作る。手順中でビルド依存を自動導入しない。PowerShellの例：

   ```powershell
   python -c "from setuptools.build_meta import build_wheel; build_wheel('dist')"
   ```

5. セル1で表示した実Pythonへ、生成した `dist/zizai_runtime-0.0.0.dev0-py3-none-any.whl` を手動導入する。PowerShellの次の2つのpathは自分の確認値へ置換する。

   ```powershell
   & '<選択カーネルのPython絶対path>' -m pip install --no-index --no-deps '<生成したwheelの絶対path>'
   ```

   `--no-deps`は実行依存が空のこの最小開発版に限る。個別コネクタを含む製品の導入方式として一般化しない。導入済みで今回のpackage内容と同じなら再導入は不要。同じ`0.0.0.dev0`でも別ビルドが導入済みの場合、pipが導入を省略することがある。その場合は、確認対象のwheelへ置き換える意図を確認したうえで上記コマンドに`--force-reinstall`を加え、標準カーネル再起動後に確認する。版が一致するだけで今回のcheckoutを検証したとみなさない。pipがない、版が合わない等は未成立として記録し、別のPythonへの導入を成功の代わりにしない。

6. 導入前に同名moduleを読み込んでいた場合は、標準カーネル再起動後に確認する。sys.path追加や独自reloadで成立させない。

## 確認ケース

| ID | 操作 | 期待結果・記録 |
| --- | --- | --- |
| K01 | セル1で選択カーネルを確認 | Python実版・cwdをローカル確認。共有記録へ個人の絶対pathを転記しない |
| K02 | 手動導入後、セル2とセル3を標準実行 | distributionがzizai-runtime／0.0.0.dev0、runtime_dependency_countが0。3 packageのimportに成功し、imports_match_distributionとimport_preserved_process_stateがtrue |
| K03 | VS Code標準操作でカーネルを再起動。セル1・セル2の後、セル4だけを実行 | K02と同じimport確認が成立し、previous_session_marker_absentもtrue。セル3を先に実行していないことと、標準再起動した事実を記録 |
| K04 | 同じカーネルでセル4を再実行 | 通常の再importが成立。独自の再初期化・自動pip・環境変更を要求しない |
| K05 | zizai-runtimeが未導入の別の既存検証カーネルがある場合、通常セルで`import zizai` | 通常のModuleNotFoundError。エラーがJupyter標準表示に出る。確認のために既存環境からアンインストールせず、未導入の検証環境がなければ未実施と記録 |
| K06 | 製品に実装済みのインスタンス生成・呼出し、個別SDK欠落 | 現時点では対象APIがなく未実施。架空クラスやダミーSDKで製品の合格にしない |

標準「すべて実行」でセル3→セル4を続けて実行すると、同じセッションのためprevious_session_marker_absentはfalseになる。これは再起動していないことを示す診断であり、独自の実行停止ではない。K03は指定したセルの実行順で確認する。

## 共有する結果

- 対象branch／commit、VS CodeとPython／Jupyter拡張の版、実施日とK01〜K06の合格／不合格／未実施。
- セル3とセル4の診断JSON。runtimeには実Python・OS・CPU・ipykernelの配布版、distributionには名前・版・Python条件・依存数を含む。filesのhashは読込先のディスクファイルの値。
- 失敗時は例外型と、秘密値・個人pathを取り除いた説明。環境変数一覧、認証情報、セル1の出力、実データは共有しない。

診断JSONの出所一致はimportされたmoduleのファイルと配布metadataのファイルの対応を確認するもので、動作・新版コードのキャッシュ更新・個別SDK・契約資産の合格を意味しない。共有前にNotebookの全出力を消去し、実行結果は[Issue #24](https://github.com/tomohiro-ono-works/vscode-extension-zizai/issues/24)へ記録する。クラウドの独立テストと、ここでのVS Code／選択カーネルの結果は区別する。
