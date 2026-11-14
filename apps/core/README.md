# ZizAI Python最小基盤

## Notebookフォーム（TASK-010、開発版0.0.1.dev0）

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
