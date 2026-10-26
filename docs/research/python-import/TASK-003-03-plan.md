# Python最小パッケージ Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 責務別のPythonソースを1つのwheelへ収集し、手動導入後に通常importできる最小基盤を作る。

**Architecture:** `zizai`と`zizai.core`の正本はapps/core、`zizai.connectors`はapps/connectorsに置く。rootの配布metadataで3 packageを明示収集し、通常Pythonのimportと例外に委ねる。個別アクション・契約生成器・VSIXは追加しない。

**Tech Stack:** Python標準unittest／venv、pip、setuptools.build_meta。確認時に利用できる既存ツールを使い、ビルド依存の追加導入は行わない。

**Spec:** [TASK-003-02](TASK-003-02.md)の「003で具体化する最小実装範囲」「003-04の独立確認ケース」。

## Global Constraints

- distributionは`zizai-runtime`、importは`zizai`。3つのpackageを1つの純Python wheelへ収める。
- コネクタ・SDKをroot importで一括読込しない。import時にcwd・環境変数・sys.pathを変更しない。
- 既存Jupyterカーネルと標準セル実行を使い、独自Engine・実行・変数同期・自動pipを追加しない。
- 初回はパッケージ入口のみで、個別処理のSDK依存は空。全採用コネクタを含む製品依存集合とは区別する。
- 初期版は出荷前を表す`0.0.0.dev0`。最小基盤のPython宣言は`>=3.12`とし、3.12・3.13で独立確認する。製品全体の最低版・全対応版の決定とは区別し、候補3.14は未検証として残す。
- root pyprojectは003のパッケージ宣言として追加する。006のlock・CI・VSIX・ZIP・デバッグ設定は変更しない。ビルド依存はsetuptoolsのPEP 621対応下限`>=61`を宣言し、製品向けの固定版は006で扱う。
- AGENTS.mdが参照する現行coding-rulesはローカルで未収録、GitHub mainでも404。旧アプリの規則を代用せず、確認できたAGENTS・文書役割・本Issueの制約と了承されたpackage正本に従う。規則不足は残る入力として記録する。
- 利用者の継続依頼に基づく今回の対象は003の最小パッケージと独立テスト。005の契約資産や004のアクションは仮実装しない。

## Review Focus

1. core以外のソースrootがwheelから落ちないこと：wheel一覧とsdistからの再ビルドで確認する。
2. 開発checkoutやcwdから偶然importできてしまわないこと：新規venvの導入前・導入後を、別cwd・`-I`で比較する。
3. 将来の全SDKの一括importを入口に追加してしまわないこと：隔離環境で対象SDKのimportを拒否するfinderを置き、実packageのimportを確認する。
4. ビルド時に別領域のPython・UI・作業データを収録しないこと：コピーしたsource treeに無関係の資産を加え、実wheelの収録内容を検査する。
5. importが利用者のcwd・環境・探索pathを書き換えないこと：隔離プロセスのimport前後を比較する。

## Task 1: 配布境界を検証する独立テスト

**Files:** Create `tests/unit/python/test_package_distribution.py`。

**Interfaces:** 実際のroot pyprojectとapps配下の正本から、一時コピー内でsetuptools backendを呼ぶ。生成wheelを使い捨てvenvへ`pip --python ... install --no-index --no-deps`で導入する。既存Python環境は変更しない。

- [ ] 収録・sdist再ビルド・導入前後のimport・不要SDK非読込・プロセス状態保持の5テストを書く。実backend・wheel・venvを使う。
- [ ] `python -m unittest discover -s tests/unit/python -p 'test_*.py' -v`を実行する。pyproject未作成を原因とする失敗を確認する。

## Task 2: 最小packageと配布宣言

**Files:** Create `pyproject.toml`、`apps/core/src/zizai/__init__.py`、`apps/core/src/zizai/core/__init__.py`、`apps/connectors/src/zizai/connectors/__init__.py`、`apps/core/README.md`。

**Interfaces:** publicなimportは`zizai`、`zizai.core`、`zizai.connectors`。個別関数・クラスの公開APIはまだ定義しない。metadata名は`zizai-runtime`、package-dirは`zizai`→coreのroot、`zizai.connectors`→connectorsのrootを明示する。

- [ ] pyprojectに最小metadata、空の実行依存、明示package一覧とpackage-dir、不要package dataを収録しない設定を追加する。
- [ ] 3つのpackage入口を作成する。入口はdocstringのみとし、必要性のない共有関数や自動処理を追加しない。
- [ ] core READMEに正本→wheelの経路、最小開発版の範囲、ビルド・テストの実在コマンドと未検証事項を記載する。
- [ ] Task 1のテストを実行し、5件が通ることを確認する。

## Task 3: 対象版・文書と受け渡し

**Files:** Create `tests/unit/python/README.md`。必要な結果はIssue #22／#23に記録する。設計資料の最小構成との差分は本計画とcore READMEから参照できるようにする。

- [ ] `ZIZAI_TEST_PYTHON=/usr/bin/python3.13 python -m unittest discover -s tests/unit/python -p 'test_*.py' -v`で同じ確認をPython3.13のvenvにも実行する。backendは確認用Python3.12の既存環境で使い、実行先の版と区別する。
- [ ] READMEと相対参照・差分空白を確認する。対象3.14・Jupyter実機、個別コネクタの依存欠落・共有関数等は未実施として記録する。
- [ ] 最小パッケージとテストを設計PRから分離したDraft PRで共有する。全コネクタ実装・003全体の完成として扱わない。
