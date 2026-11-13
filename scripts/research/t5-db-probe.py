"""Disposable real-engine research fixture; not Guildboard persistence code.

Uses only a pre-existing, explicitly pinned local image. No ports, pulls, host
mounts or shared networks. Only resources carrying this invocation's label may
be killed or removed. Synthetic root account has no password inside network=none.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import queue
import re
import subprocess
import threading
import time
import uuid


SCHEMA = """
CREATE DATABASE t5_research;
USE t5_research;
CREATE TABLE boards (
 guild VARCHAR(20) NOT NULL, board VARCHAR(36) NOT NULL,
 lineage VARCHAR(36) NOT NULL, revision BIGINT UNSIGNED NOT NULL,
 generation BIGINT UNSIGNED NOT NULL, content VARCHAR(100) NOT NULL,
 PRIMARY KEY(guild,board)
) ENGINE=InnoDB;
CREATE TABLE receipts (
 guild VARCHAR(20) NOT NULL, board VARCHAR(36) NOT NULL,
 lineage VARCHAR(36) NOT NULL, actor VARCHAR(20) NOT NULL,
 operation VARCHAR(36) NOT NULL, digest CHAR(64) NOT NULL,
 revision BIGINT UNSIGNED NOT NULL,
 PRIMARY KEY(guild,board,lineage,actor,operation),
 UNIQUE KEY revision_identity(guild,board,lineage,revision),
 FOREIGN KEY(guild,board) REFERENCES boards(guild,board)
) ENGINE=InnoDB;
CREATE TABLE events (
 guild VARCHAR(20) NOT NULL, board VARCHAR(36) NOT NULL,
 lineage VARCHAR(36) NOT NULL, revision BIGINT UNSIGNED NOT NULL,
 payload VARCHAR(100) NOT NULL,
 PRIMARY KEY(guild,board,lineage,revision),
 FOREIGN KEY(guild,board,lineage,revision)
 REFERENCES receipts(guild,board,lineage,revision)
) ENGINE=InnoDB;
CREATE TABLE outbox (
 guild VARCHAR(20) NOT NULL, board VARCHAR(36) NOT NULL,
 lineage VARCHAR(36) NOT NULL, revision BIGINT UNSIGNED NOT NULL,
 delivery VARCHAR(20) NOT NULL DEFAULT 'pending',
 PRIMARY KEY(guild,board,lineage,revision),
 FOREIGN KEY(guild,board,lineage,revision)
 REFERENCES events(guild,board,lineage,revision)
) ENGINE=InnoDB;
CREATE TABLE snapshots (
 guild VARCHAR(20) NOT NULL, board VARCHAR(36) NOT NULL,
 lineage VARCHAR(36) NOT NULL, revision BIGINT UNSIGNED NOT NULL,
 schema_version INT NOT NULL, content VARCHAR(100) NOT NULL, digest CHAR(64) NOT NULL,
 PRIMARY KEY(guild,board,lineage,revision),
 FOREIGN KEY(guild,board) REFERENCES boards(guild,board)
) ENGINE=InnoDB;
INSERT INTO boards VALUES ('1','board-a','lineage-a',0,0,'empty');
INSERT INTO boards VALUES ('2','board-b','lineage-b',0,0,'foreign');
"""


def operation(number: int) -> str:
    # Fixed synthetic SQL, not an input parser or production command adapter.
    return f"""
START TRANSACTION;
SELECT generation FROM boards WHERE guild='1' AND board='board-a' FOR UPDATE;
UPDATE boards SET revision={number},content='state-{number}'
 WHERE guild='1' AND board='board-a' AND lineage='lineage-a';
INSERT INTO receipts VALUES
 ('1','board-a','lineage-a','actor-a','op-{number}',REPEAT('{number}',64),{number});
INSERT INTO events VALUES ('1','board-a','lineage-a',{number},'state-{number}');
INSERT INTO outbox(guild,board,lineage,revision)
 VALUES ('1','board-a','lineage-a',{number});
"""


class Probe:
    def __init__(self, engine: str, image: str):
        self.engine, self.image = engine, image
        self.context = subprocess.check_output(
            ["docker", "context", "show"], text=True
        ).strip()
        self.run_id = "guildboard-t5-" + uuid.uuid4().hex[:12]
        self.name, self.volume = self.run_id + "-db", self.run_id + "-data"
        self.label = "tech.complete.guildboard.t5.run"
        self.cli = "mysql" if engine == "mysql" else "mariadb"
        self.report = {
            "evidence_kind": "isolated-real-database-fixture-not-product-or-vps",
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "engine": engine, "requested_image": image, "docker_context": self.context,
            "run_id": self.run_id, "checks": [],
            "limits": {"cpus": 1, "memory_bytes": 805306368,
                       "pids": 256, "network": "none", "published_ports": []},
        }

    def command(self, *args: str, data: str | None = None, timeout: int = 90,
                check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["docker", "--context", self.context, *args], input=data,
            text=True, encoding="utf-8", capture_output=True, timeout=timeout,
            check=check,
        )

    def verify_owner(self, kind: str, name: str) -> None:
        inspected = json.loads(self.command(kind, "inspect", name).stdout)[0]
        labels = inspected["Config"]["Labels"] if kind == "container" else inspected["Labels"]
        if (labels or {}).get(self.label) != self.run_id:
            raise RuntimeError("refusing mutation of resource without invocation ownership")

    def sql(self, sql: str, database: str = "t5_research", check: bool = True) -> str:
        result = self.command("exec", "-i", self.name, self.cli, "-uroot",
                              "--batch", "--raw", "--skip-column-names",
                              "--skip-reconnect", database, data=sql, check=check)
        if not check:
            return str(result.returncode) + "\n" + result.stderr
        return result.stdout.strip()

    def record(self, ident: str, condition: bool, details: object) -> None:
        self.report["checks"].append({"id": ident, "result": "pass" if condition else "fail",
                                      "details": details})
        if not condition:
            raise RuntimeError("research assertion failed: " + ident)
        print(self.engine + ": " + ident + " passed", flush=True)

    def ready(self) -> None:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            # Entrypoint's temporary initialization server must not count as ready.
            proc = self.command("exec", self.name, "cat", "/proc/1/comm", check=False)
            if proc.stdout.strip() in ("mysqld", "mariadbd"):
                result = self.command("exec", self.name, self.cli, "-uroot",
                                      "--batch", "--execute=SELECT 1", check=False)
                if result.returncode == 0:
                    return
            time.sleep(0.5)
        raise RuntimeError("isolated engine did not become ready within 90 seconds")

    def start(self) -> None:
        info = json.loads(self.command("image", "inspect", self.image).stdout)[0]
        self.report["image_id"] = info["Id"]
        self.report["repo_digests"] = info["RepoDigests"]
        self.command("volume", "create", "--label", self.label + "=" + self.run_id, self.volume)
        # Docker returns success for an existing named volume without relabeling it.
        # Never mount it until ownership has been observed on the actual resource.
        self.verify_owner("volume", self.volume)
        env = "MYSQL_ALLOW_EMPTY_PASSWORD=yes" if self.engine == "mysql" else "MARIADB_ALLOW_EMPTY_ROOT_PASSWORD=1"
        self.command(
            "run", "--detach", "--pull=never", "--name", self.name,
            "--label", self.label + "=" + self.run_id, "--network=none",
            "--cpus=1", "--memory=768m", "--pids-limit=256",
            "--mount", "type=volume,src=" + self.volume + ",dst=/var/lib/mysql",
            "--env", env, info["Id"], "--innodb-buffer-pool-size=64M",
            "--innodb-flush-log-at-trx-commit=1", "--sync-binlog=1",
            "--log-bin=t5-bin", "--server-id=51",
        )
        self.ready()
        self.sql(SCHEMA, database="mysql")
        self.report["server_version"] = self.sql("SELECT VERSION();")
        self.report["variables"] = self.sql(
            "SHOW VARIABLES WHERE Variable_name IN "
            "('innodb_flush_log_at_trx_commit','sync_binlog','log_bin',"
            "'innodb_doublewrite','innodb_flush_method','transaction_isolation','tx_isolation');"
        ).splitlines()

    def session(self, sql: str) -> tuple[subprocess.Popen, queue.Queue]:
        process = subprocess.Popen(
            ["docker", "--context", self.context, "exec", "-i", self.name,
             self.cli, "-uroot", "--batch", "--raw", "--skip-column-names",
             "--skip-reconnect", "--unbuffered", "t5_research"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", bufsize=1,
        )
        lines = queue.Queue()

        def collect():
            for line in process.stdout:
                lines.put(line.strip())
            lines.put(None)

        threading.Thread(target=collect, daemon=True).start()
        process.stdin.write(sql + "\n")
        process.stdin.flush()
        return process, lines

    @staticmethod
    def barrier(lines: queue.Queue) -> list[str]:
        received = []
        while True:
            line = lines.get(timeout=25)
            if line is None:
                raise RuntimeError("SQL session exited before witness marker: " + repr(received))
            if line == "T5_BARRIER":
                return received
            received.append(line)

    def crash_at(self, sql: str) -> None:
        process, lines = self.session(sql + "; SELECT 'T5_BARRIER'; SELECT SLEEP(45);")
        try:
            self.barrier(lines)
            self.verify_owner("container", self.name)
            self.command("kill", "--signal=KILL", self.name)
            process.wait(timeout=15)
            self.command("start", self.name)
            self.ready()
        finally:
            if process.poll() is None:
                process.kill()  # Own docker-exec client only, never WSL or daemon.
            process.communicate(timeout=15)

    def bundle(self, database: str = "t5_research") -> str:
        return self.sql("""
SELECT 'B',guild,board,lineage,revision,generation,content FROM boards ORDER BY guild,board;
SELECT 'R',guild,board,lineage,actor,operation,digest,revision
 FROM receipts ORDER BY guild,board,lineage,actor,operation;
SELECT 'O',guild,board,lineage,revision,delivery FROM outbox ORDER BY guild,board,lineage,revision;
SELECT 'E',guild,board,lineage,revision,payload FROM events ORDER BY guild,board,lineage,revision;
SELECT 'S',guild,board,lineage,revision,schema_version,content,digest
 FROM snapshots ORDER BY guild,board,lineage,revision;
""", database=database)

    def exercise(self) -> None:
        self.sql(operation(1) + "COMMIT;")
        baseline = self.bundle()
        self.crash_at(operation(2))
        self.record("D01-uncommitted-crash-rollback", self.bundle() == baseline,
                    "Uncommitted board/receipt/event/outbox all absent after SIGKILL + restart.")
        self.crash_at(operation(2) + "COMMIT;")
        self.record("D02-committed-crash-survival", self.sql(
            "SELECT revision,(SELECT COUNT(*) FROM receipts),(SELECT COUNT(*) FROM events),"
            "(SELECT COUNT(*) FROM outbox) "
            "FROM boards WHERE guild='1' AND board='board-a';") == "2\t2\t2\t2",
            "Commit witness observed before process kill; durable bundle survived. No application ACK modeled.")
        baseline = self.bundle()
        duplicate = self.sql("INSERT INTO receipts VALUES ('1','board-a','lineage-a',"
                             "'actor-a','op-1',REPEAT('9',64),1);", check=False)
        foreign = self.sql("INSERT INTO receipts VALUES ('2','board-a','lineage-a',"
                           "'actor-a','op-x',REPEAT('9',64),9);", check=False)
        self.record("D03-scoped-constraints", "1062" in duplicate and "1452" in foreign
                    and self.bundle() == baseline,
                    "Duplicate identity rejected 1062; foreign composite parent rejected 1452; no fixture changes.")

        selection = ("SELECT revision,(SELECT COUNT(*) FROM receipts),"
                     "(SELECT COUNT(*) FROM events),(SELECT COUNT(*) FROM outbox),content "
                     "FROM boards WHERE guild='1' AND board='board-a';")
        process, lines = self.session("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ; "
                                      "START TRANSACTION WITH CONSISTENT SNAPSHOT;" + selection
                                      + "SELECT 'T5_BARRIER';")
        try:
            initial = self.barrier(lines)
            self.sql(operation(3) + "COMMIT;")
            process.stdin.write(selection + "COMMIT; SELECT 'T5_BARRIER';\n")
            process.stdin.flush()
            second = self.barrier(lines)
            self.record("D04-consistent-cut-with-concurrent-writer",
                        initial == ["2\t2\t2\t2\tstate-2"] and second == initial
                        and self.sql(selection) == "3\t3\t3\t3\tstate-3",
                        {"snapshot_before": initial, "snapshot_after": second,
                         "current_after_writer": self.sql(selection)})
        finally:
            if process.poll() is None:
                process.stdin.close()
                process.wait(timeout=15)

        self.sql("INSERT INTO snapshots VALUES ('1','board-a','lineage-a',2,1,'state-2',SHA2('state-2',256));")
        snapshot = self.sql("SELECT content,digest FROM snapshots WHERE guild='1' AND board='board-a';")
        tail = self.sql("SELECT revision,payload FROM events WHERE guild='1' AND board='board-a' "
                        "AND lineage='lineage-a' AND revision>2 ORDER BY revision;")
        expected_hash = hashlib.sha256(b"state-2").hexdigest()
        self.record("D07-checkpoint-plus-ordered-tail", snapshot == "state-2\t" + expected_hash
                    and tail == "3\tstate-3" and self.sql("SELECT content FROM boards "
                    "WHERE guild='1' AND board='board-a';") == "state-3",
                    "Persisted observed cut 2 and hash; one ordered after-state fixture event reconstructs state-3. "
                    "Not a canvas reducer, automated snapshot publisher or compaction proof.")

        self.sql("""
START TRANSACTION;
SELECT generation FROM boards WHERE guild='1' AND board='board-a' FOR UPDATE;
UPDATE boards SET lineage='lineage-restored',revision=0,generation=generation+1,content='state-1'
 WHERE guild='1' AND board='board-a';
UPDATE outbox SET delivery='retired' WHERE guild='1' AND board='board-a';
COMMIT;
""")
        baseline = self.bundle()
        historical = self.sql("SELECT lineage,revision,digest FROM receipts WHERE guild='1' "
                              "AND board='board-a' AND lineage='lineage-a' AND actor='actor-a' AND operation='op-3';")
        stale_rows = self.sql("UPDATE boards SET content='forbidden' WHERE guild='1' "
                              "AND board='board-a' AND lineage='lineage-a'; SELECT ROW_COUNT();")
        self.record("D05-restore-preserves-retired-receipts",
                    historical == "lineage-a\t3\t" + "3"*64 and stale_rows == "0"
                    and self.bundle() == baseline,
                    "New lineage/fence, old receipts preserved; stale conditional update affects zero rows. "
                    "This is fixture SQL, not the application's read-before-receipt decision implementation.")

        dumper = "mysqldump" if self.engine == "mysql" else "mariadb-dump"
        options = ["--single-transaction", "--quick", "--skip-comments", "--no-tablespaces"]
        if self.engine == "mysql":
            options.append("--set-gtid-purged=OFF")
        dump = self.command("exec", self.name, dumper, "-uroot", *options, "t5_research").stdout
        self.sql("CREATE DATABASE t5_restored;")
        self.sql(dump, database="t5_restored")
        restored = self.bundle("t5_restored")
        self.record("D06-logical-restore-row-equality", restored == baseline,
                    {"dump_utf8_sha256": hashlib.sha256(dump.encode()).hexdigest(),
                     "canonical_fixture_rows_sha256": hashlib.sha256(restored.encode()).hexdigest(),
                     "restore_target": "fresh separate schema on the same isolated engine"})

    def cleanup(self) -> None:
        # Creation can succeed in the daemon even when the client times out.
        # Inspect exact invocation names regardless of how far start() returned.
        errors = []
        for kind, name in (("container", self.name), ("volume", self.volume)):
            try:
                exists = self.command(kind, "inspect", name, check=False)
                if exists.returncode == 0:
                    self.verify_owner(kind, name)
                    if kind == "container":
                        self.command("rm", "--force", name)
                    else:
                        self.command("volume", "rm", name)
            except Exception as error:
                # Still attempt the other exact resource; never remove anything
                # whose own ownership check failed.
                errors.append(f"{kind}: {error}")
        if errors:
            raise RuntimeError("; ".join(errors))
        self.report["cleanup"] = {
            "container_absent": self.name not in self.command(
                "ps", "--all", "--format", "{{.Names}}"
            ).stdout.splitlines(),
            "volume_absent": self.volume not in self.command(
                "volume", "ls", "--format", "{{.Name}}"
            ).stdout.splitlines(),
            "ownership_labels_checked_before_mutation": True,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("mysql", "mariadb"), required=True)
    parser.add_argument("--image", required=True, help="pre-existing repository@sha256 digest")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(args.engine + r"@sha256:[0-9a-f]{64}", args.image):
        parser.error("explicit engine repository@sha256 digest required; no mutable tag/pull")
    probe = Probe(args.engine, args.image)
    failed = False
    try:
        probe.start()
        probe.exercise()
        probe.report["result"] = "pass"
    except Exception as error:
        failed = True
        probe.report.update(result="fail", error_type=type(error).__name__, error=str(error))
    finally:
        try:
            probe.cleanup()
        except Exception as error:
            failed = True
            probe.report.update(result="fail", cleanup_error=str(error))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes((json.dumps(probe.report, indent=2, sort_keys=True) + "\n").encode())
    print(probe.engine + ": " + probe.report["result"], flush=True)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
