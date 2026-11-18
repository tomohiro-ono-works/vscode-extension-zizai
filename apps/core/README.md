# ZizAI Python最小基盤

## DuckDBフォーム（TASK-013、担当ブランチ）

Notebookのカーネルと同じPython環境に開発版のwheelを `[forms,duckdb]` 付きで導入します。[DuckDB資産](../../connectors/duckdb/)を共通フォルダーの `duckdb/` に置き、`configure_connectors` で登録してからカーネルを再起動します。`%form` で「DuckDB」→「DBファイル作成」を選び、設定後に生成コードを実行するとDBファイルの情報が `db_info` に入ります。既存DBを指定した場合は中のテーブルを保持します。

## Excelフォーム（TASK-012、開発版）

`zizai_runtime-0.0.3.dev0-py3-none-any.whl[forms,excel]`をNotebookのカーネルと同じPython環境に導入します。CSVも使う場合は`[forms,csv,excel]`を指定します。[Excel資産の正本](../../connectors/excel/)の`excel_connector.py`と`excel_definition.yaml`を共通フォルダーの`excel/`へ配置します。既にCSVを登録した環境でも、Excelを追加したら`configure_connectors`で同じ共通フォルダーを再登録し、カーネルを再起動してください。

`%load_ext zizai.forms`と`%form`でフォームを表示します。Excelの通常読み込み・範囲読み込み・書き出しから選び、生成コードをPythonセルへ貼って実行してください。範囲読み込みのヘッダー行とデータ開始行は、指定範囲の先頭を1とします。書き出し先の既定は`output.xlsx`の`シート1`です。`create_or_replace`は対象シートを置換し、`create_or_insert`は既存の対象シートの末尾にヘッダーなしで追記します。生成コードは通常の`import excel_connector`を使います。

## CSVフォーム（TASK-011、開発版0.0.3.dev0）

操作ボタンはコード欄下で`コード生成`→`コードをコピー`の順に横配置します。Windowsのコピーは標準`Set-Clipboard`を非表示プロセスで呼び、コードをUTF-8の標準入力データとして渡します。54テストと、実フォームの1クリックコピーを別プロセスから読む確認が合格。コピーのためのTkウィンドウはWindowsでは作りません。以前のTk方式・コピー未確認という記述は当時の履歴です。ユーザー試用とmain反映は継続中です。

外観は薄灰色とグリーン、上置きラベル、36pxの入力欄・プルダウン・ボタンに統一しています。フォーム内だけへ適用する`form.css`を配布物へ同梱します。Python53テスト、配布導入、VS Code上の色・高さ・配置とコード生成の確認が合格。専用Notebook`csv-form-current-20261116.ipynb`で表示しています。既存表示の更新には、フォーム表示セルで`%reload_ext zizai.forms`の後に`%form`を実行してください。実クリップボードとネイティブダイアログの前面維持、利用者の最終確認、main反映は未完了です。

参照画面が背面へ回る報告を受け、Tk親を選択中だけ最前面にする修正を追加しました。関連フォーム13テスト合格、試用環境へ導入済み。実画面での改善は確認待ちです。既に開いている選択画面には反映されないため、いったん選択／取消後、カーネル再起動と`%form`再実行で反映してください。

フォルダー選択は、保存先・入力フォルダー欄のすぐ横の`参照…`ボタンから開きます（ダブルクリック案からの利用者承認済み変更）。関連52テストと更新wheelの導入・部品配置の確認が合格。最新配置の画面描画・ネイティブダイアログ実操作は未確認です。

追加変更：文字コード・区切り文字を横配置とし、`sjis`を候補へ追加しました。読込は`df = csv_connector.read_csv(...)`、生成結果はコード欄と「コードをコピー」ボタンで表示します。コピーはローカルPythonの標準Tkを使い、ボタン押下時だけ行います。関連51テストが合格。画面描画と実クリップボード操作は未確認で、保存先ダブルクリックは未実装です。試用環境のカーネルを再起動し、`%form`を実行すると更新が反映されます。

2026-11-16の追加指示により、生成コードはパス・設定値を変数へ代入してから引数へ渡します。関連47テストと更新wheelの導入・生成確認が合格。起動中のカーネルには再起動後に反映します。この変更後のNotebook操作は未確認です。

CSVの読込・書出と、通常の`import csv_connector`を使うコード生成を追加しています。関連45テスト、実wheelの導入・登録と2つのcwdからの通常import、同じVS Codeプロファイルでフォーム→生成コードの入力・実行→CSV読込・書出が合格しました。利用者の手動確認・main反映は未完了です。

CSV依存は2026-11-15に公開情報・PyPI／OSVで既知脆弱性を確認した最新安定版のpandas 3.1.1／NumPy 2.5.4へ更新しました。動作確認済みのVS Codeで、フォームの生成コードをセルへ入力・実行するCSV読込→書出のPlaywright確認も合格しています。これを利用者の手動確認や他環境の合格へ振り替えません。

選択するPython環境へ`zizai_runtime-0.0.3.dev0-py3-none-any.whl[forms,csv]`を導入します。[CSV資産の正本](../../connectors/csv/)の`csv_connector.py`・`csv_definition.yaml`を任意の共通フォルダーの`csv/`へ一度配置します。CSV本体はwheelへ同梱せず、各分析プロジェクトへの複製も不要です。

```python
from zizai.connectors import configure_connectors
configure_connectors("D:/shared/connectors")  # このPython環境へ一度登録
```

選択したPython環境の`site-packages/zizai-connectors.json`と`zizai-connectors.pth`へ保存します。Notebookごとの登録ではありません。登録後に新しいカーネルを使うと、初期化コードなしで通常importできます。共有フォルダーを移動したら再登録し、Python環境を変えたらその環境でも登録します。初回設定にはPython環境への書込権限が必要です。既存の同名.pthがZizAI管理でなければ変更しません。明示パス、`ZIZAI_CONNECTORS_DIR`、保存設定の順でフォームの定義を参照し、`ZIZAI_CONFIG_FILE`による設定分離・従来のYAML直接指定も維持します。旧`%APPDATA%/ZizAI/settings.json`は環境内設定がない場合のみ参照します。

定義ファイルや`ZIZAI_CONNECTORS_DIR`を切り替えても、Pythonの検索先は自動変更しません。別の共有元のコードを使うときは、そのPython環境で再登録してください。標準importの名前衝突や読み込み済みモジュールの扱いは、Pythonの通常の動作に従います。

```python
%load_ext zizai.forms
%form
```

CSV・読み込みを選んで設定し、生成コードを通常のPythonセルへコピーして実行するとDataFrameを返します。書き出しでは入力変数・保存先・ファイル名を確認して実行します。既存ファイルは上書きされます。同じフォームでアクションを切り替えると有効な値を保持するため、ファイル名も確認してください。生成だけではモジュールimportやファイルの読み書きはしません。存在・権限等は実行時にPythonが確認します。

外部YAMLは`module_file: csv_connector.py`で同じフォルダーのPythonモジュールを指定します。生成コードは通常の`import csv_connector`です。登録・フォーム表示・生成だけでコネクタをimportせず、利用者が生成コードを実行したときに読み込みます。共有元の同名モジュールに注意し、更新後はカーネルを再起動してください。外部定義が未配置のコネクタは同梱定義の仮表示です。[CSVの未実行サンプル](../../examples/csv-form.ipynb)を参照してください。

### キャッシュ

`PYTHONPYCACHEPREFIX`をカーネル起動前に設定すると、キャッシュを指定先へ集約できます。初回登録で作る`.pth`の最小起動設定は、未指定の`sys.pycache_prefix`だけを利用者PC側の`%LOCALAPPDATA%/ZizAI/pycache`へ設定します。既存の指定は尊重します。登録したPython環境のプロセス全体へ適用され、共通フォルダーへのキャッシュ生成を避けます。コネクタ・業務コードは起動時に実行しません。CSV処理本体を高速化する機能ではありません。[採用方針・根拠](../../docs/features/requirements.md)を参照してください。

## Notebookフォーム（TASK-010当時の記録、開発版0.0.1.dev0）

独自VS Code拡張を使わず、Pythonコードセルの`%form`から出力欄へフォームを表示する実装を追加しています。**現在の生成結果は`{csv.importのコードを生成}`等の仮表示です。実際のCSV／Excel処理コードを生成・実行する機能はありません。** Python関連24テストと配布確認、専用Windows／VS Code InsidersでのPlaywright操作確認を実施済みです。利用者が実際のフォルダー選択・取消時の保持・仮表示の選択とコピーを確認しました。[検証範囲と制限](../../docs/research/notebook-ui/evidence/python-form-preview-20261112.json)を参照してください。

### 導入と表示

ローカルPython 3.12以降と既存のVS Code Python／Jupyter環境を使用します。開発・CLI確認環境はWindows／Python 3.14です。フォームにはipywidgets 8.1.9とPyYAML 6.0.3を使い、通常の最小基盤からはオプションとして分離しています。Jupyter公式プロジェクトと公式依存の採用条件・出典は[要件](../../docs/features/requirements.md)に記録しています。

選択カーネルに配布wheelのforms extraを導入します。NotebookのPythonセルからの例（実際のwheelパスへ置き換える）：

```python
%pip install "C:/配布先/zizai_runtime-0.0.1.dev0-py3-none-any.whl[forms]"
```

必要に応じて標準のカーネル再起動後、次を実行します。

```python
%load_ext zizai.forms
%form
```

上部のコネクタ・アクション・フォルダー選択・生成ボタンは横並びで、幅が狭い場合は折り返します。コネクタに応じてアクション候補を、コネクタ・アクションの組み合わせに応じて詳細設定を切り替えます。有効な選択・同じ型の設定は保持し、無効な選択は解除します。

`*`は必須項目です。未選択・必須の空欄・不正な値では生成できません。生成すると、フォームの下にコピー可能な仮表示を出します。入力を変えると古い仮表示を消し、次に生成した結果で置き換えます。Notebookのセル追加・source書換え・処理の自動実行は行いません。

フォルダー選択ボタンはPython標準TkのOSダイアログを開きます。ローカルGUIとTkが必要です。選択結果は絶対パス、取消では既存値を保持します。絶対パスの手入力も可能です。リモートカーネルでは利用者PCのダイアログになるとは限らず、Remote／WSL／他OSは未確認です。

### 設定ファイル

省略時は同梱の[forms.yaml](src/zizai/forms.yaml)を使います。独自のファイルを指定すると、その全体を使います。拡張機能用`.vscode/zizai-definitions.yaml`とは別の形式です。

```python
%form "C:/設定/zizai-form.yaml"
```

相対パスはカーネルの作業ディレクトリー基準です。Notebookの保存場所を自動判定しません。設定を変更したら`%form`を再実行してください。既に表示したフォームは自動更新しません。

```yaml
version: 1
output_template: "{connector}.{action}のコードを生成"
connectors:
  csv:
    label: CSV
    actions:
      import:
        label: 読み込み
        fields:
          folder: {label: 入力フォルダー, type: folder, required: true}
          encoding: {label: 文字コード, type: choice, choices: [utf-8, cp932], default: utf-8}
          start_row: {label: 開始行, type: integer, default: 1, minimum: 1}
```

| 設定 | 意味 |
| --- | --- |
| `connectors`／`actions`のキー | 選択ID。英字・数字・アンダースコア。表示文の置換に使う |
| `label` | 画面上の日本語等の表示名 |
| `fields` | そのアクションで表示する入力項目 |
| `type` | `text`、`choice`、`folder`、`integer` |
| `required` | 必須なら`true`。省略時は`false` |
| `choices` | `choice`用の重複しない文字列一覧 |
| `default` | 初期値。整数は省略時に`minimum`または0、選択は未選択、文字列は空欄 |
| `minimum` | `integer`の下限 |
| `output_template` | `{connector}`と`{action}`だけを置換する仮表示の文。外側に`{…}`が付く |

入力値はPython側のモデルで受け取ります。YAMLの内容・表示文・入力値をPythonとして評価しません。1MiB超・重複キー・alias・独自オブジェクトタグ・不正な形式は拒否します。HTMLへ表示する結果はエスケープします。

### Python APIと実装の責務

```python
from IPython.display import display
from zizai.forms import create_form

form = create_form()  # またはcreate_form("C:/設定/zizai-form.yaml")
display(form.root)
# 画面で選択した後、form.model.valuesで入力値、form.resultで生成結果を参照できる
```

`form_definition.py`は設定読込、`form_model.py`は選択・入力確認・仮表示、`forms.py`は表示・フォルダー選択・マジック登録を担当します。importだけでUIやダイアログを開かず、`%form`も明示した`%load_ext`まで登録しません。同名の他のマジックは上書きしません。カーネル再起動後は再登録・再表示が必要で、フォーム設定の自動復元は未実装です。

[未実行サンプルNotebook](../../examples/python-form.ipynb)と[フォームのCLI確認](../../tests/unit/python/README.md)を参照してください。フォーム用extraを選ばなければ従来の最小基盤の通常importにUI依存を要求しません。

## 保持した最小基盤の記録

> 2026-11-08：本書は保持した既存Python最小基盤の説明です。旧設計へのリンクは履歴参照であり、新方式への採用・完成を意味しません。

distributionは`zizai-runtime`、importは`zizai`です。当時の`0.0.0.dev0`はパッケージ入口を確認する開発版で、個別コネクタ・業務処理・契約生成器は含みません。現在のフォーム追加は上記に区別します。

## 正本から配布物への経路

| 正本 | wheel内 |
| --- | --- |
| `apps/core/src/zizai/__init__.py` | `zizai/__init__.py` |
| `apps/core/src/zizai/core/__init__.py` | `zizai/core/__init__.py` |
| `apps/connectors/src/zizai/connectors/__init__.py` | `zizai/connectors/__init__.py` |

rootの`pyproject.toml`がpackage一覧とソースの対応を明示します。生成されたwheelやsdistのコピーを直接編集せず、上記正本を更新して再ビルドします。Python側でHost・UI・他コネクタ・SDKを自動読込しません。

実行依存は最小基盤では空です。個別アクションを追加した際に必要な直接依存を宣言します。この開発版を、全コネクタに必要な依存や契約資産が揃った製品版として扱いません。共通関数は実際に複数の利用箇所が必要になった時点で追加します。

## 独立確認

リポジトリ直下で、setuptoolsとpipがあるPython環境から実行します。標準unittestを使い、pytestは不要です。テスト用pipは`--python`に対応する22.3以降を使います。

```sh
python -m unittest discover -s tests/unit/python -p 'test_*.py' -v
```

テストはソースを一時領域へコピーし、既存のsetuptools backendでwheel・sdistを生成します。別cwd・日本語と空白を含む使い捨てvenvへの手動導入を確認し、依存のネットワーク取得や既存Python環境への導入は行いません。詳しくは[独立テストの手順](../../tests/unit/python/README.md)を参照してください。

setuptoolsが導入済みの開発環境でwheelを作る最小入口は、リポジトリ直下から次を実行する方法です。build backendを直接使うコマンドであり、006の標準frontend・固定版・製品配布コマンドが確定した意味ではありません。

```sh
python -c 'from setuptools.build_meta import build_wheel; build_wheel("dist")'
```

作成したwheelは、Notebookで選択するカーネルと同じPythonへ明示的に手動導入します。生成される通常セルへpip・展開先・sys.path操作を埋め込みません。カーネル再起動後は通常の初期化セルを再実行します。

## 確認範囲

この最小基盤のPython要件は3.12以降です。製品全体の正式な最低版・対応範囲とは区別します。初回検証基準候補のWindows／Python3.14、選択Jupyterカーネル、VSIX／ZIP全体、個別処理・SDK・認証の適合は別途確認します。

[設計](https://github.com/tomohiro-ono-works/vscode-extension-zizai/blob/65631504f146a4dfa2ab52d557e58db53c2e6a00/docs/research/python-import/TASK-003-02.md)と[最小実装計画](https://github.com/tomohiro-ono-works/vscode-extension-zizai/blob/65631504f146a4dfa2ab52d557e58db53c2e6a00/docs/research/python-import/TASK-003-03-plan.md)を参照してください。
