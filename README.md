# gdrivemgr

Google Drive を **安全に操作するための Python ライブラリ**。
いきなり Drive を変更せず、**Plan（計画）を作成 → 確認 → Apply（適用）** という安全フローで操作します。

---

## 目次

* [プロジェクト概要](#プロジェクト概要)
* [使用技術](#使用技術)
* [主な機能](#主な機能)
* [セットアップ手順](#セットアップ手順)
* [使い方](#使い方)
* [ディレクトリ構成](#ディレクトリ構成)
* [実装上の工夫](#実装上の工夫)
* [開発者向け情報](#開発者向け情報)
* [使用パッケージ一覧](#使用パッケージ一覧)
* [ライセンス](#ライセンス)

---

## プロジェクト概要

gdrivemgr は Google Drive を直接変更せず、

1. 差分の **Plan（操作計画）を作成**
2. Plan を人間が確認
3. 問題なければ **Apply（適用）**

という安全設計を採用した Python ライブラリです。

### 🎯 目的

* MOVE / DELETE の事故防止
* Drive上の更新衝突（modified_time不一致）の検出
* 削除順序の自動正規化
* 安全な運用フローの標準化

---

## 使用技術

* Python 3.10+
* Google Drive API v3
* OAuth 2.0 認証
* unittest（テスト）

---

## 主な機能

### v1で実装済み

* フォルダ作成（CREATE_FOLDER）
* リネーム（RENAME）
* 移動（MOVE）※単一親のみ
* コピー（COPY）※ファイルのみ
* ゴミ箱へ移動（TRASH）
* 完全削除（DELETE_PERMANENT）
* ファイルアップロード（UPLOAD_FILE）
* ファイルダウンロード（DOWNLOAD_FILE）

### v1で非対応

* PCディレクトリとのミラー同期
* フォルダコピー
* 複数親アイテムのMOVE
* Google Docs系のダウンロード

---

## セットアップ手順

### 1. ライブラリインストール

#### 相対パスからインストール
```bash
pip install -e .
```

#### GitHubからインストール
```bash
pip install gdrivemgr@git+https://github.com/Swimmy-Tachikawa/gdrivemgr.git
```

### 3. 必要パッケージ

gdrivemgrのインストール時に自動的にインストールされなかった場合、以下を実行してインストール
```bash
pip install google-api-python-client google-auth google-auth-oauthlib
```

---

## OAuth準備

必要ファイル：

* `client_secrets.json`
* `token.json`（初回は自動生成）

```python
from gdrivemgr import AuthInfo

auth = AuthInfo(
    kind="oauth",
    data={
        "client_secrets_file": "/ABS/PATH/client_secrets.json",
        "token_file": "/ABS/PATH/token.json",
    },
)
```

---

## 使い方

### 基本フロー（最重要）

```python
from gdrivemgr import AuthInfo, GoogleDriveManager

auth = AuthInfo(
    kind="oauth",
    data={
        "client_secrets_file": "/ABS/PATH/client_secrets.json",
        "token_file": "/ABS/PATH/token.json",
    },
)

mgr = GoogleDriveManager(auth)

root_id = "YOUR_TEST_ROOT_FOLDER_ID"

# 1. スナップショット取得
local = mgr.open(root_id)

# 2. Localで操作を積む
new_id = local.create_folder("tmp", root_id)

# 3. Plan生成
plan = mgr.build_plan()

# 4. Apply
result = mgr.apply_plan(plan)

print(result.status)
print(result.summary)
```

---

### 安全原則

* Planを必ず確認してからApply
* rootは必ずテスト用フォルダID
* DELETE_PERMANENTは基本使わない
* ConflictError発生時はopenからやり直す

---

## ディレクトリ構成

```
gdrivemgr/
│
├── auth/
│   ├── auth_info.py
│   └── oauth_client.py
│
├── controller/
│   └── drive_controller.py
│
├── local/
│   ├── snapshot.py
│   ├── validators.py
│   └── google_drive_local.py
│
├── plan/
│   ├── action.py
│   ├── plan_operation.py
│   ├── sync_plan.py
│   ├── ordering.py
│   └── preconditions.py
│
├── models/
│   ├── file_info.py
│   ├── operation_result.py
│   └── sync_result.py
│
├── manager.py
└── __init__.py
```

---

## 実装上の工夫

### 1. Plan → Apply の安全設計

Driveを即時変更せず、操作を蓄積してから適用。

---

### 2. modified_time による衝突検出

Plan生成時の modified_time を保持し、Apply時に一致確認。

一致しない場合：

```
ConflictError
```

---

### 3. 削除系の順序正規化

TRASH / DELETE が連続する場合のみ：

* 深い階層 → 浅い階層

に並び替え。

---

### 4. Fail-Fast設計

非致命エラー発生時：

* 例外で全停止させない
* SyncResultで停止箇所を返却

致命例外：

* AuthError
* PermissionError
* InvalidStateError
* InvalidArgumentError

は即送出。

---

## 開発者向け情報

### アーキテクチャ

```
AuthInfo
    ↓
OAuthClient
    ↓
GoogleDriveController
    ↓
GoogleDriveLocal
    ↓
SyncPlan
    ↓
GoogleDriveManager
```

### Localの本質

* PCのミラーではない
* Driveスナップショットの仮想状態

---

### テスト戦略

* unitテスト：純粋ロジック
* mockテスト：controller差し替え
* integration：テスト用rootのみで実Drive検証

---

## 使用パッケージ一覧

* google-api-python-client
* google-auth
* google-auth-oauthlib
* unittest（標準ライブラリ）

---

## ライセンス

MIT License
