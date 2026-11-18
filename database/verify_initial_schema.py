#!/usr/bin/env python3
"""Install or verify the ordered, empty-schema v0 to v1 migration."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import select
import subprocess
import time

SOURCE = Path(__file__).parent / "migrations/0001_initial_innodb.sql"
SOURCE_DIGEST = "045A76201BD00C399905A7E19B4F50C74DD141D00CA06EDED8F3225C91987F8D"
MYSQL = "8.4.11"
MARIADB = "11.4.13-MariaDB-ubu2404"
BINARY_SET = "schema-v1"
MODE = "STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION"
# One SHA-256 of escaped SHOW CREATE TABLE output per statement, in SQL order.
# The exact engines emit different catalog text, including implicit FK indexes.
CATALOG = {
    MYSQL: (
        "4FCD0CF0827DA59D16B1DF27990E3D9EC5EA5A09830F80970993CB5F95E57469",
        "34DA97FFF732FFD97B74C0CEB14D332845E81CAD2173464E0DC890830C208A15",
        "A50B72F3F01FE90A320F32A55D5C12856DD4B54DF612E3B044EF812B5B3C6766",
        "6F7ED92439316013FCE92BC3D01A570F9C3C68CFBBB87CBA0F1E5555F8717373",
        "C74C78F517027A5C329A85B603AA73509A103425AE8D760262AE508C4D4B249D",
        "642DEED641043EFED0809CA5C6A3CC4A2284F1F8D47DD37B138BBD5CDCFF1273",
        "EA7F1DFDF1FFD319B29A2F2A19F095E8756DEDEAEC77D86E4D20AE62F855B31D",
        "47691CB705CC72CBEEE2B7E3C4A6D73676D654AFE3B502EDC395BA20A52AE60B",
        "58880E91626BEA9774D79072310E41A135A4BE673CF9F518F2F1978585F99575",
        "EC2607AD8FB1A8581082D506F25C80BFCD73A4391C1701AF36D3512D4B22F67A",
        "91F2CD387DF8069F183E4794EF6EF6926FF32A317751F7A41C97A9C4C6A91E1F",
        "92989952F9436136AA81C956E2D48AB9117FE3F227E22C39BB7F8698940A7837",
        "863F24EF6F6980B74CF8BAA7C61F6AFB7BE11722CD5177DCAEE5B8FD5D06F26F",
        "29AC9BBD5856D85E6CCB4E4CC9935E9A355B47BD07FF48A9D02ACD8B446380FD",
        "533EA193F89B63A96C1C1D945FE294AE948FB352DCCF93EE5F24A99F61716801",
        "471BF96F4698422B6486DF18FC3780F08EC52C41E0D8F6686946ACE22B39096D",
        "36DBDF236CA622860110545E7892BEBE5F6AB0DD0707F6F3C342798C50B0B16A",
        "930FB1DB753F191B6C612557B39F535F549D74989F9AB06B6C5D1217FBF08F9D",
        "4A56CC1006768E19A25221AB914D8724694EDD98112E6044990FA2182E44A389",
        "1B13CB35315269884C79BC48A4CCDDD31117A0C8D22CEC750B433D1B79AD73B0",
    ),
    MARIADB: (
        "0049BB06E457F176C2831C052A507A76F6FFE852D1D989F31094C2DBB85D1A21",
        "6ADA6BE60E3F4D55A2748265B2ADA54805C4F258897FB64091759A7B00736B28",
        "CF90EDDB1753443999193EEF98A31D8FC6201C8CC53B2F63A6B681907C90B437",
        "6F7ED92439316013FCE92BC3D01A570F9C3C68CFBBB87CBA0F1E5555F8717373",
        "297B6E8C61D9781B7B86559654F01601D74D46A9EDB17D5E81CF6D1570D8EB98",
        "2F44178BA498D3C15ED141FD8F40C4D41E1818BA90FD9AB98D04AFDFFAF5FD01",
        "DB8DAC28331F2B7803B2900A94629E07D843629A54C94CAB81932E9EA172DD13",
        "FE89D93A3BCC7980DE04E65418865E69009BDB0FBD28B909302923DA63C3D1A1",
        "24A705584E4F63D738C2AB41F943B85B02FD46D274601DDD6DCD2A1694302333",
        "3F02274BAB616216319CF4D1EC8CAC0DD04F44F36FEB8D0B52A84996E8CE01FA",
        "0EF4594340E345BBEB657358769799B6B893E9145BAA56BE3442000D4927CE42",
        "B3F95D2EA9BCB1E18A967F9236771EE00DDEE74ED848DA9BA56BBCE885A58DC5",
        "EBF3AA98317809DDD6A57CC623C0CA9C8EBC58B4BFA26F0CD78718CDCCE7909B",
        "66966CDE5F7A449B9DF16EB7EF98B984732D8D957935560A71CD3E646F5CC8A6",
        "FC343B0C3C05179A36FD19FC92A3E8B0384BE16D39625AA56A52C77DCE5F20C3",
        "F209F6A25919090109C5AD121F88AA851CA1EBD64272734F15627770697A2A5A",
        "36DBDF236CA622860110545E7892BEBE5F6AB0DD0707F6F3C342798C50B0B16A",
        "B6D265C0D0B30944A9AD1C22B3F0D00AF80C23FF35DA2C90ED823B27AB6711E4",
        "3FE0B5B47545515565427E593486EEF6B4E995F3D3BF20B9D016ED27DC612B41",
        "C4A91D033E1109D3D46D3B361B2FD2F6C0938E370F66E5F0ED58A677030C35C7",
    ),
}


class Fenced(RuntimeError):
    pass


def statements(source):
    ddl = re.sub(rb"(?m)^--[^\n]*\n", b"", source).decode("ascii")
    return tuple(part.strip() for part in ddl.split(";") if part.strip())


def sha(value):
    return hashlib.sha256(value).hexdigest().upper()


class Session:
    def __init__(self, argv, database):
        self.client = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=0,
        )
        self.database = database
        self.buffer = b""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.client.stdin.close()
        try:
            self.client.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.client.kill()
            self.client.wait()
        finally:
            self.client.stdout.close()

    def query(self, sql):
        # No SQL comes from remote input. The client exits at the first SQL
        # error. A missing terminator means no more statements may be issued.
        marker = b"-- guildboard result end --"
        try:
            request = sql.encode("ascii") + b";\nSELECT '" + marker + b"';\n"
            if self.client.stdin.write(request) != len(request):
                raise Fenced("incomplete SQL request")
        except BrokenPipeError as error:
            raise Fenced("SQL session ended") from error
        finish = time.monotonic() + 30
        lines = []
        while True:
            line, sep, remainder = self.buffer.partition(b"\n")
            if sep:
                self.buffer = remainder
                if line == marker:
                    return lines
                lines.append(line)
                continue
            remaining = finish - time.monotonic()
            if remaining <= 0 or not select.select([self.client.stdout], [], [], remaining)[0]:
                raise Fenced("SQL session timed out")
            chunk = os.read(self.client.stdout.fileno(), 65536)
            if not chunk:
                raise Fenced("SQL statement failed or session ended")
            self.buffer += chunk


def preflight(session):
    rows = session.query(
        "SELECT VERSION(), DATABASE(), @@global.skip_networking, @@session.autocommit"
    )
    try:
        version, db, private, autocommit = rows[0].decode("ascii").split("\t")
    except (IndexError, ValueError):
        raise Fenced("could not identify storage session") from None
    if version not in CATALOG or db != session.database or (private, autocommit) != ("1", "1"):
        raise Fenced("unsupported engine, database, or session settings")
    session.query("SET NAMES ascii COLLATE ascii_bin")
    session.query(
        f"SET SESSION sql_mode='{MODE}', foreign_key_checks=1, unique_checks=1, sql_quote_show_create=1"
    )
    if version == MARIADB:
        session.query("SET SESSION check_constraint_checks=1")
    return version


def catalog_tables(session):
    rows = session.query(
        "SELECT TABLE_NAME, TABLE_TYPE FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA=BINARY DATABASE()"
    )
    tables = set()
    for row in rows:
        name, _, kind = row.partition(b"\t")
        if kind != b"BASE TABLE" or not re.fullmatch(rb"[a-z_]+", name):
            raise Fenced("unrecognized catalog object")
        tables.add(name.decode("ascii"))
    for table, schema in (("TRIGGERS", "TRIGGER_SCHEMA"), ("EVENTS", "EVENT_SCHEMA"),
                          ("ROUTINES", "ROUTINE_SCHEMA")):
        if session.query(f"SELECT 1 FROM information_schema.{table} WHERE {schema}=BINARY DATABASE() LIMIT 1"):
            raise Fenced("unexpected trigger, event, or routine")
    return tables


def fingerprint(session, name):
    rows = session.query(f"SHOW CREATE TABLE `{name}`")
    if len(rows) != 1 or not rows[0].startswith(name.encode("ascii") + b"\t"):
        raise Fenced("unrecognized table definition")
    # Constraint clause order does not affect this schema. Keep column and
    # index order and normalize the named clauses and their final delimiter.
    lines = rows[0].split(rb"\n")
    constraints = [line.rstrip(b",") for line in lines if line.startswith(b"  CONSTRAINT ")]
    remainder = [line for line in lines if not line.startswith(b"  CONSTRAINT ")]
    return sha(b"\n".join([*remainder, *sorted(constraints)]))


def migration(session, generation, apply):
    source = SOURCE.read_bytes()
    digest = sha(source)
    if digest != SOURCE_DIGEST:
        raise Fenced("migration source digest differs")
    ddl = statements(source)
    expected = CATALOG[preflight(session)]
    if len(ddl) != len(expected):
        raise Fenced("migration manifest does not match source")
    targets = [re.match(r"(?:CREATE|ALTER) TABLE ([a-z_]+)\s", sql)[1] for sql in ddl]
    if session.query("SELECT GET_LOCK(CONCAT('gb.v1:', SHA2(DATABASE(),224)),0)") != [b"1"]:
        raise Fenced("schema session already owned")

    def check_prefix(length, next_allowed=False):
        tables = catalog_tables(session)
        actual = {name: fingerprint(session, name) for name in tables}
        acceptable = [dict(zip(targets[:length], expected[:length]))]
        if next_allowed:
            acceptable.append(dict(zip(targets[:length + 1], expected[:length + 1])))
        for offset, candidate in enumerate(acceptable):
            if actual == candidate:
                return length + offset
        raise Fenced(f"catalog differs from recorded migration progress at step {length}")

    journal = "schema_installation"
    if not catalog_tables(session):
        if not apply:
            raise Fenced("schema v1 is not activated")
        session.query(ddl[0])
    if journal not in catalog_tables(session) or fingerprint(session, journal) != expected[0]:
        raise Fenced("unrecognized migration journal")

    rows = session.query(
        f"SELECT migration_id, source_version, target_version, HEX(migration_digest), "
        "HEX(storage_generation), compatible_binary_set, owner_epoch, completed_steps, phase "
        f"FROM {journal} WHERE singleton=1"
    )
    identity = f"1\t0\t1\t{digest}\t{generation}\t{BINARY_SET}\t".encode("ascii")
    if not rows and apply:
        check_prefix(1)
        session.query(
            f"INSERT INTO {journal} VALUES (1,1,0,1,X'{digest}',X'{generation}',"
            f"'{BINARY_SET}',0,1,'planned')"
        )
        rows = [identity + b"0\t1\tplanned"]
    if len(rows) != 1 or not rows[0].startswith(identity):
        raise Fenced("migration identity, generation, or compatible binary set differs")
    epoch_str, completed_str, phase = rows[0][len(identity):].split(b"\t")
    epoch, completed = int(epoch_str), int(completed_str)
    if phase == b"activated" and completed == len(ddl):
        check_prefix(completed)
        return
    if not apply or phase != b"planned" or not 1 <= completed <= len(ddl) or epoch == 2**64 - 1:
        raise Fenced("unsupported migration phase or exhausted owner fence")

    actual = check_prefix(completed, next_allowed=completed < len(ddl))
    for name in set(targets[1:actual]):
        if session.query(f"SELECT 1 FROM `{name}` LIMIT 1"):
            raise Fenced("unexpected application data before activation")
    session.query(f"UPDATE {journal} SET owner_epoch={epoch + 1} WHERE singleton=1")
    for index in range(completed, len(ddl)):
        if index >= actual:
            session.query(ddl[index])
        check_prefix(index + 1)
        session.query(
            f"UPDATE {journal} SET completed_steps={index + 1} "
            f"WHERE singleton=1 AND owner_epoch={epoch + 1}"
        )
    # This initial install has no backfill or destructive contraction. A
    # non-activated catalog cannot be used by an application startup.
    session.query(
        f"UPDATE {journal} SET phase='activated' "
        f"WHERE singleton=1 AND owner_epoch={epoch + 1} AND completed_steps={len(ddl)}"
    )
    if session.query(f"SELECT phase FROM {journal} WHERE singleton=1") != [b"activated"]:
        raise Fenced("activation did not persist")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", type=Path, required=True, help="absolute path to verified SQL client")
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--generation", required=True, help="trusted 128-bit generation as lowercase hex")
    parser.add_argument("--apply", action="store_true", help="explicitly install or resume an isolated v1 schema")
    args = parser.parse_args()
    if (
        not re.fullmatch("[a-z][a-z0-9_]{0,63}", args.database)
        or args.database in {"mysql", "sys", "performance_schema", "information_schema"}
        or not re.fullmatch("[0-9a-f]{32}", args.generation)
        or not args.client.is_absolute() or not args.socket.is_absolute()
        or not args.client.is_file() or not args.socket.is_socket()
        or os.environ.get("MYSQL_PWD") is not None
    ):
        parser.error("invalid local fixture arguments")
    # Oracle's client reads login paths even with --no-defaults.
    argv = [str(args.client), "--no-defaults"]
    if args.client.name == "mysql":
        argv.append("--no-login-paths")
    argv.extend([
        "--protocol=socket", f"--socket={args.socket}", f"--user={args.user}",
        f"--database={args.database}", "--batch", "--skip-column-names", "--unbuffered",
        "--skip-reconnect", "--binary-mode", "--connect-timeout=3",
    ])
    try:
        with Session(argv, args.database) as session:
            migration(session, args.generation.upper(), args.apply)
    except (Fenced, OSError) as error:
        parser.exit(1, f"schema fenced ({error if isinstance(error, Fenced) else 'local SQL client unavailable'})\n")
    print("schema v1 activated and verified")


if __name__ == "__main__":
    main()
