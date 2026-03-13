# gdrivemgr

Google Drive を **安全に（事故なく）操作するための Python ライブラリ**です。
Drive を「いきなり実行」せず、**Plan（計画）→ レビュー → Apply（適用）** の手順を必須にすることで、

* MOVE/DELETE の順序ミス
* 誤った root を操作してしまう事故
* 他者更新との衝突（更新競合）

などを減らすことを目的としています。

> **重要**: gdrivemgr は「PCのフォルダを同期するツール」ではありません。
> Drive の状態を読み込んだ **仮想状態（Local）** を操作し、Plan を作ってから Drive に反映します。

---

## 目次

* [1. gdrivemgrとは（最重要コンセプト）](#1-gdrivemgrとは最重要コンセプト)
* [2. できること／できないこと（v1の制約）](#2-できることできないことv1の制約)
* [3. 導入（インストール／必要ライブラリ）](#3-導入インストール必要ライブラリ)
* [4. OAuth準備（client_secrets.json と token.json）](#4-oauth準備client_secretsjson-と-tokenjson)
* [5. 一般利用（基本の使い方）](#5-一般利用基本の使い方)

  * [5-1. 最短クイックスタート（Plan→Apply）](#5-1-最短クイックスタートplanapply)
  * [5-2. Local操作（操作の積み上げ）](#5-2-local操作操作の積み上げ)
  * [5-3. Planの確認（事故防止の要）](#5-3-planの確認事故防止の要)
  * [5-4. Apply結果（SyncResult）の読み方](#5-4-apply結果syncresultの読み方)
  * [5-5. よくある運用パターン](#5-5-よくある運用パターン)
  * [5-6. 代表的なエラーと対処](#5-6-代表的なエラーと対処)
* [6. Localで可能な操作（API一覧＋具体例）](#6-localで可能な操作api一覧具体例)
* [7. 内部実装の概要（仕組みを理解して運用したい人向け）](#7-内部実装の概要仕組みを理解して運用したい人向け)

  * [7-1. アーキテクチャ（auth/controller/local/plan/manager）](#7-1-アーキテクチャauthcontrollerlocalplanmanager)
  * [7-2. Localは「PCミラー」ではない（仮想状態）](#7-2-localはpcミラーではない仮想状態)
  * [7-3. 同一判定（FileID）と同名許容](#7-3-同一判定fileidと同名許容)
  * [7-4. apply_order（順序正規化）の規則](#7-4-apply_order順序正規化の規則)
  * [7-5. precondition（modified_time一致）と衝突検出](#7-5-preconditionmodified_time一致と衝突検出)
  * [7-6. 例外ポリシー（致命／非致命、Fail-Fast）](#7-6-例外ポリシー致命非致命fail-fast)
  * [7-7. supportsAllDrives とスコープ（権限）](#7-7-supportsalldrives-とスコープ権限)
  * [7-8. テスト戦略（unit / mock / integration）](#7-8-テスト戦略unit--mock--integration)
  * [7-9. 実運用での安全チェックリスト](#7-9-実運用での安全チェックリスト)
* [8. ディレクトリ構成](#8-ディレクトリ構成)
* [9. 使用パッケージ一覧](#9-使用パッケージ一覧)
* [10. ライセンス](#10-ライセンス)

---

## 1. gdrivemgrとは（最重要コンセプト）

gdrivemgr は「Google Drive をいきなり操作しない」ためのライブラリです。

### 基本思想

1. **Plan（計画）を作る**
2. **Plan を人間が確認する**（ここが事故防止の核心）
3. 問題がなければ **Apply（適用）** で Drive に反映する

この 1→2→3 によって、

* MOVEの順番ミス
* DELETEを先に入れてしまった
* 他人がDrive上で更新して衝突した

などの事故を減らすことを目的にしています。

Planは `SyncPlan`、Applyすると `SyncResult` が返ります。

---

## 2. できること／できないこと（v1の制約）

### できること（v1）

* フォルダ作成（CREATE_FOLDER）
* リネーム（RENAME）
* 移動（MOVE）※単一親のみ
* コピー（COPY）※ファイルのみ（フォルダコピー不可）
* ゴミ箱へ移動（TRASH）
* 完全削除（DELETE_PERMANENT）※危険。通常運用は非推奨
* アップロード（UPLOAD_FILE）
* ダウンロード（DOWNLOAD_FILE）※Google Docs系は不可

### できないこと（v1）

* PC上のディレクトリを同期する「ミラーリング」機能

  * Localは仮想状態であり、PCのファイルシステム操作はしません
* フォルダのコピー（Local側で禁止）
* 複数親（ショートカット等）を持つアイテムの MOVE（禁止）
* Google Docs/Sheets/Slides などのダウンロード（v1では禁止）

---

## 3. 導入（インストール／必要ライブラリ）

> 開発中・ローカルリポジトリ運用の例です。

### 3-1. 仮想環境

```bash
python -m venv venv
source venv/bin/activate
```

### 3-2. インストール（編集可能モード）

```bash
pip install -e .
```

### 3-3. Google API クライアント系（必須）

```bash
pip install google-api-python-client google-auth google-auth-oauthlib
```

これらが無い場合、`OAuthClient` / `GoogleDriveManager` 初期化で認証系エラーになります。

---

## 4. OAuth準備（client_secrets.json と token.json）

gdrivemgr は v1 で OAuth を採用します。

### 必要ファイル

* `client_secrets.json`

  * Google Cloud Console で作成した OAuth クライアント secrets JSON
* `token.json`

  * 認可後のトークン保存先
  * 初回は存在しなくてもOK（認可後に自動生成）

### AuthInfo の指定例

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

### よくある失敗

* `/ABS/PATH/...` を実パスに変え忘れる

  * `FileNotFoundError` → `AuthError("OAuth authorization flow failed")`
* `token.json` 保存先のディレクトリ権限がない

  * 認可後の保存で失敗します

---

## 5. 一般利用（基本の使い方）

### 前提：root（操作対象フォルダ）運用

**テスト専用フォルダ（root）** を Drive 上に作成し、そのフォルダIDだけを操作対象にする運用を推奨します。

* 誤って本番を触る事故を避ける
* integration test の安全性が高い

---

### 5-1. 最短クイックスタート（Plan→Apply）

```python
from gdrivemgr import AuthInfo, GoogleDriveManager

# 1) OAuth設定
auth = AuthInfo(
    kind="oauth",
    data={
        "client_secrets_file": "/ABS/PATH/client_secrets.json",
        "token_file": "/ABS/PATH/token.json",
    },
)

# 2) Manager生成
mgr = GoogleDriveManager(auth)

# 3) rootは「テスト専用フォルダID」
root_id = "YOUR_TEST_ROOT_FOLDER_ID"

# 4) open：root配下のスナップショットを読み込み Local を構築
local = mgr.open(root_id)

# 5) Local操作：この時点ではDriveは変わらない（安全）
new_folder_local_id = local.create_folder("tmp", root_id)

# 6) Plan生成：何が実行されるか確認できる
plan = mgr.build_plan()

# 7) Apply：Driveへ反映
result = mgr.apply_plan(plan)

print(result.status)
print(result.summary)
```

ポイント：

* `open()` するまで Local は存在しません（スナップショットが必要）
* Local 操作は「操作の蓄積」であり **Driveは変わりません**
* `apply_plan()` した瞬間にだけ Drive が変更されます

---

### 5-2. Local操作（操作の積み上げ）

Local は「Driveの状態を読み込んだ仮想ファイルツリー」です。

Local のメソッドを呼ぶと、

* 仮想状態（スナップショット）が更新され
* `PlanOperation` が内部に蓄積されます

つまり、**Localは安全な“下書き”** です。

操作をいくつ積んでも Drive は変わらず、Plan を作って初めて「何が行われるか」が確定します。

---

### 5-3. Planの確認（事故防止の要）

Planは「適用前に目視で確認する」ことが価値です。

```python
plan = mgr.build_plan()

# 1) Planの基本情報
print("root:", plan.remote_root_id)
print("ops:", len(plan.operations))

# 2) 積まれた操作（ユーザー順 / seq順）
for op in plan.operations:
    print(
        op.seq,
        op.action.value,
        op.op_id,
        "target=", op.target_local_id,
        "parent=", op.parent_local_id,
        "new_parent=", op.new_parent_local_id,
        "name=", op.name,
        "local_path=", op.local_path,
    )

# 3) 実際の適用順（apply_order）
#    ※削除系が連続ブロックの場合のみ深い→浅いに正規化される
print("apply_order:")
for op_id in plan.apply_order:
    print(" ", op_id)
```

確認ポイント：

* `plan.remote_root_id` が意図した root か（別rootのPlanをApplyしない）
* DELETE_PERMANENT が紛れ込んでいないか
* MOVE の順序が意図通りか

---

### 5-4. Apply結果（SyncResult）の読み方

`apply_plan(plan)` は `SyncResult` を返します。

* `result.status`: `"success"` または `"failed"`
* `result.results`: `OperationResult` の配列（各 op の成否）
* `result.stopped_op_id`: Fail-Fastで止まった `op_id`（失敗時）
* `result.id_map`:

  * Localで作った item（`file_id=None`）の `local_id` → Drive上で確定した `file_id` の対応表
* `result.summary`:

  * `{"success": x, "failed": y, "skipped": z, ...}`
* `result.snapshot_refreshed`:

  * apply後に再スナップショット（refresh）できたか

**Fail-Fast** の意味：

* 非致命エラーが発生したら、その時点で止めて `failed` を返す
* 例外で全停止はしない（結果は SyncResult で把握できる）

結果の読み方例：

```python
result = mgr.apply_plan(plan)

print("status:", result.status)
print("summary:", result.summary)
print("stopped_op_id:", result.stopped_op_id)
print("snapshot_refreshed:", result.snapshot_refreshed)

for r in result.results:
    print(r.op_id, r.status, r.message)

# Localで新規作成したものの file_id 確定
print("id_map:", result.id_map)
```

---

### 5-5. よくある運用パターン

#### (1) 安全運用（人間レビュー必須）

* localで操作を積む
* planをprintして確認
* OKなら apply

#### (2) “同期風”に使う（ただし内部はPlan→Apply）

* `mgr.sync(...)` を利用（実装に合わせて使用）
* `execute=False` 相当で plan だけ生成してレビューする使い方が基本

#### (3) 事故防止の基本

* “本番フォルダ”を root にしない
* “テスト専用フォルダID”で運用に慣れる
* DELETE_PERMANENT は基本使わず TRASH で止める

---

### 5-6. 代表的なエラーと対処

#### (1) AuthError: OAuth authorization flow failed

* `client_secrets_file` が存在しない
* `token_file` の保存先ディレクトリ権限がない
* 認可フローが通らない（Raspberry Piでブラウザ/ポート問題など）

対処：

* パスを実在する絶対パスにする
* token保存ディレクトリの権限を確認
* 認可URLを開ける環境で初回認可を行う

#### (2) InvalidStateError: Local is not initialized. Call open() first.

* `mgr.open(root_id)` を呼んでいない

#### (3) InvalidStateError: Plan root_id does not match current opened root.

* openしたrootと `plan.remote_root_id` が違う
* 別rootのplanをapplyしようとした

#### (4) ConflictError: modified_time mismatch

* Plan作成後〜Apply前に、Drive上で対象が更新された

対処：

* もう一度 `open()` → 操作を積み直す（新しいmodified_timeでPlanを作る）

#### (5) LocalValidationError

* root を rename/move/trash/delete しようとした
* tombstoned（削除予定）に対して rename/move しようとした
* MOVEで循環（親を子に）になる
* MOVE対象が複数親だった

---

## 6. Localで可能な操作（API一覧＋具体例）

Local は **Driveスナップショット（DriveSnapshot）** を元に構築される **仮想状態** です。

* Local操作は Drive を変更しません
* Local操作は PlanOperation を積み上げます

> 重要：Local の `*_id` は、Driveの `file_id` と同一とは限りません。
> Localで新規作成したものは `file_id=None` で、`local_id` は UUID です。Apply後に `result.id_map` でDriveの `file_id` が確定します。

以下に、Localで可能な操作を **すべて** 列挙し、目的・注意点・例を記載します。

---

### 6-1. 参照／検索系

#### get(local_id)

Local内の `FileInfo` を取得します。

```python
info = local.get(local_id)
print(info.name, info.file_id, info.modified_time)
```

#### list_children(parent_local_id)

指定フォルダ直下の子要素を列挙します。

```python
children = local.list_children(parent_id)
for c in children:
    print(c.name, c.local_id, c.file_id)
```

#### find_by_name(name, parent_local_id=None)

同名許容のため **複数件返る** 前提です。

```python
hits = local.find_by_name("report.pdf", parent_local_id=root_id)
for h in hits:
    print(h.local_id, h.file_id)
```

---

### 6-2. 操作の積み上げ（Driveは変わらない）

#### create_folder(name, parent_local_id) -> new_local_id

指定フォルダ配下にフォルダ作成を積みます。

```python
new_local_id = local.create_folder("tmp", root_id)
```

注意：

* 新規作成なので `file_id=None`
* Apply後に `id_map[new_local_id]` で Drive の file_id が確定

#### rename(target_local_id, new_name)

名前変更を積みます。

```python
local.rename(target_id, "new_name")
```

注意：

* precondition（modified_time一致）の対象
* tombstoned（削除予定）のものを rename できない

#### move(target_local_id, new_parent_local_id)

親フォルダ変更（移動）を積みます。

```python
local.move(target_id, new_parent_id)
```

注意：

* v1では **単一親のみ**
* 循環（親を子にする）は禁止
* precondition（modified_time一致）の対象

#### copy(target_local_id, new_parent_local_id, new_name=None) -> new_local_id

ファイルコピーを積みます。

```python
copied_id = local.copy(target_id, root_id, new_name="copy.txt")
```

注意：

* v1では **ファイルのみ**（フォルダコピー不可）
* precondition（modified_time一致）の対象

#### trash(target_local_id)

ゴミ箱へ移動（論理削除）を積みます。

```python
local.trash(target_id)
```

注意：

* 削除系は apply_order 正規化の対象（連続ブロック時）
* precondition（modified_time一致）の対象

#### delete_permanently(target_local_id)

完全削除（物理削除）を積みます。

```python
local.delete_permanently(target_id)
```

注意：

* **危険**：通常運用は非推奨（TRASH運用推奨）
* 削除系は apply_order 正規化の対象（連続ブロック時）
* precondition（modified_time一致）の対象

#### upload_file(local_path, parent_local_id, name=None) -> new_local_id

ファイルアップロードを積みます。

```python
new_file_id = local.upload_file("./a.txt", root_id)
```

注意：

* Local時点では Drive に存在しない（file_id=None）
* Apply時に controller がアップロードを実行

#### download_file(target_local_id, local_path, overwrite=False)

ファイルダウンロードを積みます。

```python
local.download_file(target_id, "./downloaded.bin", overwrite=False)
```

注意：

* v1では Google Docs系（Docs/Sheets/Slides 等）は不可
* precondition（modified_time一致）の対象

---

### 6-3. 操作の確認／破棄

#### list_ops() -> list[PlanOperation]

積まれた操作（PlanOperation）を列挙します。

```python
for op in local.list_ops():
    print(op.seq, op.action, op.target_local_id)
```

#### clear_ops()

積んだ操作をすべて破棄し、open直後状態に戻します。

```python
local.clear_ops()
```

運用のコツ：

* 「Planを確認して危ない」と感じたら `clear_ops()` でやり直す

---

## 7. 内部実装の概要（仕組みを理解して運用したい人向け）

### 7-1. アーキテクチャ（auth/controller/local/plan/manager）

* `auth/`

  * `AuthInfo`（認証情報の保持）
  * `OAuthClient`（CredentialsとDrive service生成）
* `controller/`

  * `GoogleDriveController`（Drive API 呼び出し層：HttpError→独自例外、リトライ）
* `local/`

  * `DriveSnapshot`（複数インデックスでDrive状態を保持）
  * `GoogleDriveLocal`（仮想状態＋操作蓄積＋Plan生成）
* `plan/`

  * `Action / PlanOperation / SyncPlan / ordering / preconditions`
* `manager.py`

  * `GoogleDriveManager`（open→Local→Plan→Apply→refreshの統括）
* `models/`

  * `FileInfo / OperationResult / SyncResult`

---

### 7-2. Localは「PCミラー」ではない（仮想状態）

重要：`GoogleDriveLocal` はローカルPCのファイルシステムを操作しません。

例：

* `local.upload_file("/tmp/a.txt", parent)`

  * Driveへ即アップロードしない
  * Planに `UPLOAD_FILE` を積む
  * Apply時に controller がアップロード

このため、ローカルディレクトリ同期のような用途には向きません。

---

### 7-3. 同一判定（FileID）と同名許容

* 同一判定は **FileID** で行います
* 同じ親フォルダ内に同名が複数存在しても許容します

そのため name検索は複数件返る可能性があります。

また、Localで作った項目は Drive未作成なので

* `file_id=None`
* `local_id=UUID`

になり、Apply後に `id_map` により Driveの `file_id` が確定します。

---

### 7-4. apply_order（順序正規化）の規則

基本：ユーザーが積んだ順（seq順）を尊重します。

ただし削除系（TRASH/DELETE_PERMANENT）が「連続ブロック」になった場合のみ、

* depth（rootからの距離）を計算し
* 深い→浅い で並び替えます

狙い：

* 親→子の順で削除して参照が壊れる／後続が失敗する、を減らす

---

### 7-5. precondition（modified_time一致）と衝突検出

対象操作（既存対象に影響するもの）

* RENAME / MOVE / TRASH / DELETE_PERMANENT / COPY / DOWNLOAD

Plan生成時に

* Localの `FileInfo.modified_time` を `expected_modified_time` としてpreconditionに付与

Apply時に

* controllerで取得した `modifiedTime` と一致するか検査
* 不一致なら `ConflictError`

これにより「Plan作成後にDrive側で変更された」衝突を検出します。

---

### 7-6. 例外ポリシー（致命／非致命、Fail-Fast）

apply は2種類の失敗を扱います。

#### 致命例外（送出して停止）

* AuthError
* PermissionError
* InvalidArgumentError
* InvalidStateError

#### 非致命エラー（例外で止めない）

* NotFoundError
* RateLimitError
* NetworkError
* ConflictError

→ `OperationResult.failed` として記録し、Fail-Fastで停止して `SyncResult.failed` を返します。

狙い：

* “途中まで進んだが、結果はSyncResultで把握できる”
* “致命なら例外で即座に止める（安全）”

の両立。

---

### 7-7. supportsAllDrives とスコープ（権限）

controllerは `supportsAllDrives` / `includeItemsFromAllDrives` を一貫して付与できます。
共有ドライブを扱う場合に重要です。

スコープ例：

* フル権限：`https://www.googleapis.com/auth/drive`
* 読み取り：`https://www.googleapis.com/auth/drive.readonly`

運用の推奨：

* まず readonly で open/list の動作を確認
* その後 drive スコープで書き込み運用へ

---

### 7-8. テスト戦略（unit / mock / integration）

* unit：モデル、Local、plan ordering、preconditions の純粋ロジックを unittest
* mock：controller を差し替えて manager.apply の挙動を検証
* integration：実Driveのテスト用フォルダ（root）配下だけで動作確認

統合テストで最重要：

* テスト用rootフォルダID以外に影響を出さない

---

### 7-9. 実運用での安全チェックリスト

* [ ] rootは必ずテスト用フォルダIDにする（本番直指定を避ける）
* [ ] Planを必ず表示して確認（特にDELETE系）
* [ ] DELETE_PERMANENT は基本使わない（TRASH運用）
* [ ] Apply前後でDrive側の更新が無いか（ConflictError）
* [ ] 失敗時は SyncResult.results を読んで stopped_op_id を確認
* [ ] snapshot_refreshed=False の場合は open をやり直す

---

## 8. ディレクトリ構成

```text
gdrivemgr/
├── auth/
├── controller/
├── local/
├── plan/
├── models/
├── manager.py
└── __init__.py
```

---

## 9. 使用パッケージ一覧

* google-api-python-client
* google-auth
* google-auth-oauthlib

---

## 10. ライセンス

MIT License
