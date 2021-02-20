# python-bind9zone

BIND9のZoneファイルをDB管理するPythonベースのCLIアプリです。

DB上で管理されたレコード情報を元にして、ローカルディレクトリ上にZoneデータを生成することで、
DB中心のDNS運用ができるようになります。

各レコードにはnamespaceが設定されており、同じZone(ORIGIN)のレコードを分類することができます。
この機能とBIND9のViewを組み合わせることで、同じFQDNへの問い合わせに対してアクセス元に応じて
異なる応答を返すDNSサーバを設計することができます。

このアプリケーションは現在アルファリリース未満です。

#### Zoneファイルの配置例

```
- {ZONEDIR}
    |
    +--- {namespace}
    |      |
    |      +--- {origin}.zone
    |      +--- {origin}.zone
    |
    +--- {namespace}
    |      |
    |      +--- {origin}.zone
    |      +--- {origin}.zone

```

## インストール

Pythonモジュールとしてインストールすると、CLIツール(bind9zone)も合わせて導入されます。python3環境が必要です。

```sh
pip install git+https://github.com/showtatsu/python-bind9zone
```

データベースにはSQLite3またはPostgreSQLをサポートしています。

## 使い方 (CLI)

SQLite3データベースを使用し、コマンドラインからローカルにあるzoneファイルをDB上に取り込みます。

```sh
# データベースにSQLite3(ローカルファイル)を選択
export DB_CONNECT="sqlite:///bindzone-db.sqlite3"
# DBを初期化
python -m bind9zone init --drop
# 既存のbind9 zoneファイルを読み込み
python -m bind9zone pushzone --zone public/example.com tests/input/public/example.com.zone

# DB上から特定のレコードを取得
python -m bind9zone get --zone public/example.com server A
# 出力例(標準出力):
# server 60 IN A 192.0.2.1

# DB上に新しいレコードを登録
# (namespace/origin内に同一の名前/タイプのレコードがある場合は上書きされます)
python -m bind9zone set --zone public/example.com new-server A 192.0.2.5

# 現在のDBの内容でbind9 zoneファイルを作成
python -m bind9zone pullzone --zone public/example.com > example.com.zone
```

ゾーンファイルを所定のディレクトリ配置にすることで、まとめて管理することができます。

```sh
# ファイルは {namespace}/{origin}.zone の形式で配置します。
# Zoneファイルの末尾は ".zone" にします。
#  
#  ./zones <--- ゾーンファイル保管用ディレクトリ (この場所をオプションで指定します)
#     |
#     +-- public   <-- public namespace のゾーンファイルが配置されます。
#     |     |
#     |     +-- example.com.zone  <-- namespace=public, origin=example.com  のZoneファイル。
#     |
#     +-- private  <-- private namespace のゾーンファイルが配置されます。
#           |
#           +-- example.com.zone  <-- namespace=private, origin=example.com のZoneファイル。
#

# DBにPostgreSQLを使用する場合、postgresql://スキーマで接続先を指定します。
export DB_CONNECT="postgresql://username:password@postgresdb.local/database"
# DBを初期化(関連するテーブルがdropされ、空のテーブルとして再度作成されます)
python -m bind9zone init --drop

# bulkpushで複数のゾーンファイルを一度にDB上に格納します。
# bulkpushはDB上に1つでも同じnamespace,originのレコードが存在すると失敗しますので
# 実行前に deletezone を使用して既存のデータを一度削除してください。
python -m bind9zone deletezone --zones public/example.com,private/example.com
python -m bind9zone bulkpush --dir ./zones --zones public/example.com,private/example.com

# bulkpullで複数のnamespace,originのゾーンファイルを一度に生成します。
python -m bind9zone bulkpull --dir ./zones --zones public/example.com,private/example.com
```


## コマンドとオプション

以下のオプションは全てのコマンドに共通です。

| コマンドラインオプション | 同等の環境変数 | 説明 | デフォルト |
| ---- | ---- | ---- | ---- |
| --connection STRING | DB_CONNECT | 接続するデータベースへの接続文字列です。 | このオプションは省略できません |

### init

接続したDBにこのアプリケーションが使用するテーブル(dns_zone_record)を作成します。

| コマンドラインオプション | 同等の環境変数 | 説明 | デフォルト |
| ---- | ---- | ---- | ---- |
| --drop | (なし) | 既存のテーブルが存在した場合はDROPする。 | FALSE |

```sh
bind9zone init --drop
```

### pullzone, pushzone

- `pushzone`は、指定したzoneファイルの内容から、DBの内容を生成して書き込みます。

- `pullzone`は、DBの内容から特定のorigin/namespaceのzoneファイルを生成して出力します。

| コマンドラインオプション | 同等の環境変数 | 説明 | デフォルト |
| ---- | ---- | ---- | ---- |
| --zone | (なし) | 対象のZoneのnamespaceとoriginを"/"で区切って指定します。 | このオプションは省略できません |
| --dir  | (なし) | zoneファイル入出力に使用するディレクトリを指定します。このディレクトリを起点に、`./{namespace}/{origin}.zone`に相当するファイルが対象になります。 | 標準入出力が使用されます |

```sh
bind9zone pullzone --zone public/example.com > example.com.zone
```

#### bulkpush

適切なディレクトリ構造にしたがって配置されたzoneファイルから、DBの内容を生成して書き込みます。

| コマンドラインオプション | 同等の環境変数 | 説明 | デフォルト |
| ---- | ---- | ---- | ---- |
| --zones | ZONES | 対象のZoneのnamespaceとoriginを"/"で区切って指定します。複数のzoneを","で繋いで複数指定できます。 | このオプションは省略できません |
| --dir  | ZONEDIR | zoneファイル入出力に使用するディレクトリを指定します。このディレクトリを起点に、`./{namespace}/{origin}.zone`に相当するファイルが対象になります。 | このオプションは省略できません |


#### bulkpull

DBの内容から指定したorigin/namespaceのzoneファイルを適切なディレクトリ構造にしたがって生成します

| コマンドラインオプション | 同等の環境変数 | 説明 | デフォルト |
| ---- | ---- | ---- | ---- |
| --zones | ZONES | 対象のZoneのnamespaceとoriginを"/"で区切って指定します。複数のzoneを","で繋いで複数指定できます。 | このオプションは省略できません |
| --dir  | ZONEDIR | zoneファイル入出力に使用するディレクトリを指定します。このディレクトリを起点に、`./{namespace}/{origin}.zone`に相当するファイルが対象になります。 | このオプションは省略できません |
| --mkdir  | (なし) | zoneファイル入出力に使用するディレクトリにnamespaceディレクトリが存在しない場合は作成します。 | FALSE |


#### deletezone

指定したorigin/namespaceのレコードを全て削除します。

| コマンドラインオプション | 同等の環境変数 | 説明 | デフォルト |
| ---- | ---- | ---- | ---- |
| --zones | ZONES | 対象のZoneのnamespaceとoriginを"/"で区切って指定します。複数のzoneを","で繋いで複数指定できます。 | このオプションは省略できません |

#### get

指定したname/typeのレコードを取得します。

| コマンドラインオプション | 同等の環境変数 | 説明 | デフォルト |
| ---- | ---- | ---- | ---- |
| --zone | (なし) | 対象のZoneのnamespaceとoriginを"/"で区切って指定します。 | このオプションは省略できません |
| 第1引数(name) | - | 取得対象のリソース名を指定します。 | このオプションは省略できません |
| 第2引数(type) | - | 取得対象のリソースタイプを指定します。(A, CNAME, TXT など) | 登録された全てのタイプが取得されます |

#### set

指定したname/typeのレコードに値を設定します。

| コマンドラインオプション | 同等の環境変数 | 説明 | デフォルト |
| ---- | ---- | ---- | ---- |
| --zone | (なし) | 対象のZoneのnamespaceとoriginを"/"で区切って指定します。 | このオプションは省略できません |
| 第1引数(name) | - | 更新対象のリソース名を指定します。 | このオプションは省略できません |
| 第2引数(type) | - | 更新対象のリソースタイプを指定します。(A, CNAME, TXT など) | このオプションは省略できません |
| 第3引数(values) | - | リソースの値を指定します。 | このオプションは省略できません |


# テスト

```sh
# ユニットテスト実行後、テストカバレッジ計算結果を ./htmlcov に保存します。
python -m pytest -v --cov=bind9zone --cov-report=html
```
