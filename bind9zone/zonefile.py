import re
import validators
import itertools
from datetime import datetime, timedelta, timezone
from .zonerecord import ZoneRecord

class ZoneFile(object):
    
    @classmethod
    def to_zonefile(cls, records, sort=True):
        """
        ZoneRecordのリストを、BIND9 zonefile 形式の str に変換して返します。
        """
        originWithDot = records[0].origin
        if sort:
            records = cls.sort_records(records)
        zonedata = '\n'.join([
            '\n'.join(['$ORIGIN {}'.format(originWithDot)]),
            '\n'.join(['$TTL {}'.format(600)]),
            '\n'.join([r.to_record() for r in records]),
        ])
        return zonedata


    @classmethod
    def from_stream(cls, reader, origin='.', ttl=None, missed_lines=None):
        """
        def get_from_zonefile

        Zoneファイルを行分割したイテレータを処理して有効な行のdictのiteratorを返します。
        各dictの戻り値は record_match を参照してください。
        処理できなかった行があると、missedLines引数の配列に格納されます。
        """
        line = reader.readline()
        lastRecord = None
        typeTopRecord = None
        skip_directives=True # Not implemented yet, Force skip directive option.
        while line:
            line = line.rstrip()
            meta = cls.parser_metadata_comment(line)
            line = cls.parser_remove_comment(line)
            if line.strip() == '':
                continue

            # $GENERATE
            generate = cls.parser_generate_directive(line, origin)
            if generate and not skip_directives:
                yield { **meta, **generate } if meta else generate
                line = reader.readline()
                continue

            # $ORIGIN, $TTL
            directive = cls.parser_generic_directive(line)
            if directive:
                if directive["name"] == '$ORIGIN':
                    if directive["data"].endswith('.'):
                        origin = directive["data"]
                    else:
                        origin = directive["data"] + '.' + origin
                elif directive["name"] == '$TTL':
                    ttl = int(directive["data"])
                else:
                    raise ValueError('Unknown directive section found in zone file. line=[{}]'.format(line))
                if not skip_directives:
                    yield { **meta, **directive } if meta else directive
                line = reader.readline()
                continue

            # Resource record lines.
            record = cls.parser_resource_record(line, origin)
            if record:
                if record["type"] != "SOA":
                    # SOAレコード以外は1行にまとまってないと駄目。

                    # nameフィールドが省略されたら、前段のレコードから取得(必須)
                    if record["name"] is None:
                        if lastRecord is not None:
                            record["name"] = lastRecord["name"]
                        else:
                            raise ValueError('Resource name omitted and last entry not found. line=[{}]'.format(line))
                    
                    # classフィールドが省略されたら、前段のレコードから取得(必須)
                    if record["class"] is None:
                        if lastRecord is not None:
                            record["class"] = lastRecord["class"]
                        else:
                            raise ValueError('Resource class omitted and last entry not found. line=[{}], dict=[{}]'.format(line, str(record)))
                    
                    # ttlフィールドは、先行する "同一名/同一typeのレコード"の値が優先されます。
                    # ただし、コードレベルではTTL値自体は登録可能ですので注意してください。
                    # 同一名/同一タイプで異なるTTLを指定した時、最初に現れたレコードの値が選択される動作はBIND9サーバの仕様です。
                    # 先行するrecordがない場合はゾーンファイルのデフォルト値から取得します。
                    if record["ttl"] is None:
                        if typeTopRecord is not None and typeTopRecord["type"] == record["type"]:
                            record["ttl"] = typeTopRecord["ttl"]
                        else:
                            record["ttl"] = ttl

                    # SOA以外のレコードはここから返ります。
                    yield { **meta, **record } if meta else record
                    lastRecord = record
                    if not (typeTopRecord is not None \
                        and typeTopRecord['name'] == record['name'] \
                        and typeTopRecord['type'] == record['type']):
                        typeTopRecord = record
                else:
                    # SOAレコードは複数行になってもOK。その代わり"("までは行にまとまってないと駄目。
                    # 追加でSOAレコードの最後まで読み込む必要があります。
                    record = cls.parser_soa_record(line, origin)
                    while record is None:
                        nextline = reader.readline()
                        if nextline is None:
                            break
                        line += ' ' + cls.parser_remove_comment(nextline)
                        record = cls.parser_soa_record(line, origin)
                        if record or len(line) > 1024:
                            break
                    if record:
                        # SOAレコードはここから返ります。
                        yield { **meta, **record } if meta else record
                        lastRecord = record
                        if not (typeTopRecord is not None \
                            and typeTopRecord['name'] == record['name'] \
                            and typeTopRecord['type'] == record['type']):
                            typeTopRecord = record
                    else:
                        # SOAを読み込むために複数行の処理を開始したが、
                        # 適切なSOAが識別できなかった場合は例外を発生させます。
                        raise Exception("Valid SOA is not found or maybe longer than 1024 bytes. Buffer='{}'".format(line))
            if missed_lines is not None and len(missed_lines) > 0 and len(line) > 0:
                raise Exception("Invalid parser: {}".format(line))
            line = reader.readline()


    @staticmethod
    def sort_records(records, types=['SOA'], names=['@']):
        """
        sort_records(records, order=[]):
        型、レコード名に応じてZoneRecordのlistをソートして返します。
        order変数にはソート時に優先されるZoneRecordのtype値を指定します。
        ソート時の優先度は、order変数に指定したtype順 -> nameのアルファベッド順 -> type順 です。
        """
        def keyfunc(r):
            if not isinstance(r, ZoneRecord):
                raise TypeError('This function only accept for a list of ZoneRecord objects.')
            typeorder = types.index(r.type) if r.type in types else 'zz'
            nameorder = names.index(r.name) if r.name in names else 'z'
            return '{}:{}:{}:{}'.format(typeorder, nameorder, r.name, r.type)
        return sorted(records, key=keyfunc)


    @staticmethod
    def parser_metadata_comment(line):
        """
        def parser_metadata_comment (line:str): => int or None
        Zoneファイルのデータ1行からコメントメタデータを読み出します。
        """
        pattern = r'^(?:[^;"]|"[^"]*")*; meta=\(id=(\d+)\)$'
        match = re.match(pattern, line)
        if match:
            return {
                "id": int(match.group(1))
            }


    @staticmethod
    def parser_remove_comment(line):
        """
        def parser_remove_comment (line:str): => str
        Zoneファイルのデータ1行からコメントを除去します
        """
        pattern = r'^(?:[^;"]|"[^"]*")*'
        match = re.match(pattern, line)
        if match:
            line = match.group(0)
        return line.rstrip()

    @staticmethod
    def parser_generic_directive(line):
        """
        def parser_generic_directive (line:str): => dict

        Zoneファイルのデータ1行からディレクティブ行($XXXX)をパースします。
        戻りがdictの場合は下記項目です。

        - name: $XXXXX の部分
        - data: $XXXXX の後ろに続くもの。name直後のスペースは無視されます。

        ディレクティブ行以外が入力された場合はNoneが返ります。
        """
        pattern = r'^(?P<name>\$[A-Za-z]+)(?:\s+(?P<data>[0-9A-Za-z.-]+|"[^"]*"))?$'
        match = re.match(pattern, line)
        if match:
            record = {
                "name": match.group("name"),
                "data": match.group("data"),
            }
            return record


    @staticmethod
    def parser_generate_directive(line, currentOrigin):
        """
        def generate_match (line:str, currentOrigin:str): => dict

        Zoneファイルのデータ1行からGENERATEディレクティブ行($GENERATE)をパースします。
        currentOriginには現在処理中のゾーンファイル上で、有効な$ORIGIN値を指定します。

        戻りはdictで下記項目です。

        - name:    "$GENERATE"
        - data:    $XXXXX の後ろに続くもの。name直後のスペースは無視されます。
        - range:   1-255 などの範囲
        - pattern: GENERATEテンプレート
        - origin:  入力されたcurrentOrigin値が入ります。

        GENERATEディレクティブ行以外が入力された場合はNoneが返ります。

          $GENERATE range lhs [ttl] [class] type rhs [comment]
          => {  name  : "range lhs",
                type  : "type",
                class : "class",
                ttl   : "ttl",
                data  : "rhs",
            }
        """
        pattern = r'^(?P<name>\$GENERATE)\s+(?P<data>(?P<range>[0-9]+-[0-9]+)\s+(?P<pattern>.+))$'
        match = re.match(pattern, line)
        if match:
            record = {
                "name": match.group("name"),
                "data": match.group("data"),
                "range": match.group("range"),
                "pattern": match.group("pattern"),
                "origin": currentOrigin,
            }
            return record


    @staticmethod
    def parser_resource_record(line, currentOrigin):
        """
        def parser_resource_record (line:str, currentOrigin:str): => dict
        
        Zoneファイルのリソースレコード1行をパースします。
        currentOriginには現在処理中のゾーンファイル上で、有効な$ORIGIN値を指定します。
        戻りはdictで下記項目です。

        - name:    リソース名(先頭)に指定された値
        - ttl:     有効期限
        - class:   リソースクラス。省力化のため、"IN"にしかマッチしませんので、常に"IN"です。
        - type:    リソースタイプ。"A"とか"AAAA"とか。
        - data:    リソースの値。typeに続く文字列が入ります。

        リソースレコード以外が入力された場合はNoneが返ります。

            lhs ttl class type rhs
            => {  name  : "lhs",
                    type  : "type",
                    class : "class",
                    ttl   : "ttl",
                    data  : "rhs",
                }

            mail.example.com. 600 IN A 10.0.0.1
            => {  name  : "mail.example.com.",
                    type  : "A",
                    class : "IN",
                    ttl   : 600,
                    data  : "10.0.0.1",
                }
        """
        pattern = r'^(?P<name>[0-9A-Za-z*._-]+|@)?\s+(?:(?P<ttl>[1-9][0-9]*[MHDW]?)\s+)?(?:(?P<class>IN)\s+)?(?:(?P<type>A|AAAA|AFSDB|APL|CAA|CDNSKEY|CDS|CERT|CNAME|DHCID|DLV|DNAME|DNSKEY|DS|HIP|IPSECKEY|KEY|KX|LOC|MX|NAPTR|NS|NSEC|NSEC3|NSEC3PARAM|PTR|RRSIG|RP|SIG|SOA|SRV|SSHFP|TA|TKEY|TLSA|TSIG|TXT)\s+)(?P<data>\S.*)$'
        match = re.match(pattern, line)
        if match:
            record = {
                "name": match.group("name"),
                "ttl": match.group("ttl"),
                "class": match.group("class"),
                "type": match.group("type"),
                "data": match.group("data"),
                "origin": currentOrigin,
            }
            return record


    @staticmethod
    def parser_soa_record(line, currentOrigin):
        """
        def parser_soa_record (line:str, currentOrigin:str): => dict

        Zoneファイルのリソースレコード1行をパースします。この関数はrecord_matchのSOAのみに反応する版です。
        currentOriginには現在処理中のゾーンファイル上で、有効な$ORIGIN値を指定します。

        戻りはdictで下記項目です。

        - name:    リソース名(先頭)に指定された値
        - ttl:     有効期限
        - class:   リソースクラス。省力化のため、"IN"にしかマッチしませんので、常に"IN"です。
        - type:    リソースタイプ。"A"とか"AAAA"とか。
        - data:    リソースの値。typeに続く文字列が入ります。

        この関数は、SOA以外のレコードにはマッチしません(Noneを返します)。
        また、SOAレコードが途中でも "(" までの文字が入っていればマッチします。
        リソースレコード以外が入力された場合はNoneが返ります。
        """
        pattern = r'^(?P<name>[0-9A-Za-z*._-]+|@)?\s+(?:(?P<ttl>[1-9][0-9]*)\s+)?(?:(?P<class>IN)\s+)?(?:(?P<type>SOA)\s+)(?P<data>(?:(?P<dns>[0-9A-Za-z.-]+)\s+)(?:(?P<email>[0-9A-Za-z.-]+)\s+)\(\s*(?P<serial>[0-9]+)\s+(?P<refresh>[0-9]+)\s+(?P<retry>[0-9]+)\s+(?P<expire>[0-9]+)\s+(?P<minimum>[0-9]+)\s*\))$'
        match = re.match(pattern, line)
        if match:
            record = {
                "name": match.group("name"),
                "ttl": match.group("ttl"),
                "class": match.group("class"),
                "type": match.group("type"),
                "data": match.group("data"),
                "origin": currentOrigin,
            }
            return record
