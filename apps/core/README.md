# ZizAI Python最小基盤

distributionは`zizai-runtime`、importは`zizai`です。現在の`0.0.0.dev0`はパッケージ入口を確認する開発版で、個別コネクタ・業務処理・契約生成器はまだ含みません。

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

[設計](../../docs/research/python-import/TASK-003-02.md)と[最小実装計画](../../docs/research/python-import/TASK-003-03-plan.md)を参照してください。
