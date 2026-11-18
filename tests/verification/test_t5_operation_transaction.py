"""Isolated InnoDB witness for the accepted v1 operation transaction."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from hashlib import sha256
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
import unittest
import uuid

import test_t5_initial_schema as initial

SCHEMA = initial.SCHEMA
FIXTURE_ENV = ("GB_SCHEMA_CLIENT", "GB_SCHEMA_SOCKET", "GB_SCHEMA_USER")
BOARD = "11" * 16
OTHER_BOARD = "22" * 16
LINEAGE = "33" * 16
PROOF = "44" * 16
OPERATION = "55" * 16
AUDIT_ID = "66" * 16
PAYLOAD = "fixture edit"
STATE = "fixture state after edit"
RECEIPT = b"fixture receipt revision 1"
SCOPE = f"guild_id='1' AND board_id=X'{BOARD}'"
HEAD_LOCK = (
    "SELECT lifecycle, HEX(active_lineage_id), active_revision, policy_generation "
    f"FROM boards WHERE {SCOPE} FOR UPDATE"
)
# Collect all five effects in one consistent statement, along with control boards.
VIEW = """
SELECT 'board', guild_id, HEX(board_id),
       CONCAT_WS('|', active_revision, policy_generation, HEX(active_lineage_id), canonical_state)
FROM boards
UNION ALL
SELECT 'receipt', guild_id, HEX(board_id),
       CONCAT_WS('|', HEX(lineage_id), actor_user_id, HEX(operation_id), revision,
                 policy_generation, digest_codec, HEX(semantic_digest), receipt_version, canonical_receipt)
FROM receipts
UNION ALL
SELECT 'event', guild_id, HEX(board_id),
       CONCAT_WS('|', HEX(lineage_id), revision, actor_user_id, HEX(operation_id),
                 event_version, kind, canonical_payload)
FROM accepted_events
UNION ALL
SELECT 'outbox', guild_id, HEX(board_id), CONCAT_WS('|', HEX(lineage_id), revision, delivery_state)
FROM outbox
UNION ALL
SELECT 'audit', guild_id, HEX(board_id),
       CONCAT_WS('|', HEX(event_id), event_version, scope_kind, actor_kind, actor_ref,
                 action_code, outcome, reason_code, policy_generation, HEX(correlation_id))
FROM audit_events
ORDER BY 1, 2, 3, 4
"""


@dataclass(frozen=True)
class Attempt:
    guild: str = "1"
    board: str = BOARD
    actor: str = "8"
    lineage: str = LINEAGE
    base: int = 0
    policy: int = 7
    payload: str = PAYLOAD
    shape_valid: bool = True
    read_allowed: bool = True
    write_allowed: bool = True


DEFAULT = Attempt()


def fixture_digest(attempt):
    # All inputs are fixed in this file. The hash is opaque fixture data.
    semantic = f"edit|{attempt.payload}|{attempt.lineage}|{attempt.base}|{attempt.policy}"
    return sha256(semantic.encode("ascii")).hexdigest().upper()


@unittest.skipUnless(all(os.environ.get(name) for name in FIXTURE_ENV), "requires disposable private SQL fixture")
class OperationTransactionTests(unittest.TestCase):
    def setUp(self):
        client = Path(os.environ["GB_SCHEMA_CLIENT"])
        socket = Path(os.environ["GB_SCHEMA_SOCKET"])
        user = os.environ["GB_SCHEMA_USER"]
        self.assertTrue(client.is_absolute() and client.is_file() and socket.is_absolute() and socket.is_socket())
        self.assertNotIn("MYSQL_PWD", os.environ)
        self.assertEqual(socket.resolve(strict=True), socket)
        self.assertEqual(socket.stat().st_uid, os.geteuid())
        fixture_root = socket.parent.stat()
        self.assertEqual(fixture_root.st_uid, os.geteuid())
        self.assertEqual(stat.S_IMODE(fixture_root.st_mode), 0o700)
        fixture_data = socket.parent / "data"
        self.assertTrue(fixture_data.is_dir() and fixture_data.resolve(strict=True) == fixture_data)
        data_metadata = fixture_data.stat()
        self.assertEqual(data_metadata.st_uid, os.geteuid())
        self.assertEqual(stat.S_IMODE(data_metadata.st_mode), 0o700)
        self.db = "gb178_" + uuid.uuid4().hex
        self.cli = [str(client), "--no-defaults"]
        if client.name == "mysql":
            self.cli.append("--no-login-paths")
        self.cli.extend([
            "--protocol=socket", f"--socket={socket}", f"--user={user}", "--connect-timeout=3",
            "--batch", "--skip-column-names", "--unbuffered", "--skip-reconnect", "--binary-mode",
        ])

        def admin(sql):
            return subprocess.run(
                [*self.cli, "-e", sql], capture_output=True, text=True, timeout=10, check=True,
            ).stdout.strip()

        version, private, datadir = admin(
            "SELECT VERSION(), @@global.skip_networking, @@global.datadir"
        ).split("\t")
        self.assertIn(version, SCHEMA.CATALOG)
        self.engine_version = version
        self.assertEqual(private, "1")
        self.assertEqual(Path(datadir).resolve(strict=True), fixture_data)
        admin(f"CREATE DATABASE {self.db}")
        self.addCleanup(admin, f"DROP DATABASE {self.db}")
        result = subprocess.run(
            [sys.executable, "-B", str(initial.TOOL), "--client", str(client), "--socket", str(socket),
             "--user", user, "--database", self.db, "--generation", initial.GENERATION, "--apply"],
            capture_output=True, text=True, check=True, timeout=60,
        )
        self.assertEqual(result.stdout.strip(), "schema v1 activated and verified")

        with self.connection() as owner:
            SCHEMA.preflight(owner)
            owner.query("INSERT INTO guilds VALUES ('1','active'),('2','active')")
            for guild, board in (("1", BOARD), ("1", OTHER_BOARD), ("2", BOARD)):
                scope = f"'{guild}',X'{board}'"
                predicates = f"guild_id='{guild}' AND board_id=X'{board}'"
                owner.query(
                    "INSERT INTO boards (guild_id,board_id,name,lifecycle,active_revision,policy_generation,"
                    f"state_codec,canonical_state) VALUES ({scope},'fixture','initializing',0,7,1,'fixture baseline')"
                )
                owner.query(f"INSERT INTO lineages VALUES ({scope},X'{LINEAGE}','creation',NULL,NULL,NULL,0,NULL)")
                owner.query(f"INSERT INTO receipt_coverage VALUES ({scope},0,X'{PROOF}',X'{LINEAGE}',0,'fixture')")
                owner.query(f"INSERT INTO receipt_coverage_lineages VALUES ({scope},0,X'{PROOF}',X'{LINEAGE}')")
                owner.query(
                    f"UPDATE boards SET lifecycle='active', active_lineage_id=X'{LINEAGE}', recovery_generation=0, "
                    f"coverage_proof_id=X'{PROOF}' WHERE {predicates}"
                )

    def connection(self):
        return SCHEMA.Session([*self.cli, f"--database={self.db}"], self.db)

    def stage(self, session, attempt=DEFAULT):
        """Stage a fixture decision in the caller's socket-bound session."""
        if not attempt.shape_valid:
            return "INVALID_SHAPE"
        if not attempt.read_allowed or (attempt.guild, attempt.board, attempt.actor) != ("1", BOARD, "8"):
            return "CONCEALED"

        digest = fixture_digest(attempt)
        session.query("START TRANSACTION")
        head, = session.query(HEAD_LOCK)
        lifecycle, lineage, revision, policy = head.decode("ascii").split("\t")
        receipt = session.query(
            f"SELECT HEX(semantic_digest), canonical_receipt FROM receipts WHERE {SCOPE} "
            f"AND lineage_id=X'{attempt.lineage}' AND actor_user_id='8' AND operation_id=X'{OPERATION}'"
        )
        if receipt:
            retained, = receipt
            old_digest, original = retained.split(b"\t")
            return original if old_digest.decode("ascii") == digest else "IDEMPOTENCY_CONFLICT"

        if not attempt.write_allowed or lifecycle != "active":
            return "CONCEALED"
        if attempt.lineage != lineage:
            return "LINEAGE_CHANGED"
        if attempt.policy != int(policy):
            return "POLICY_STALE"
        if attempt.base != int(revision):
            return "CONFLICT"
        self.assertEqual(
            session.query(f"SELECT final_revision IS NULL FROM lineages WHERE {SCOPE} AND lineage_id=X'{lineage}'"),
            [b"1"],
        )

        next_revision = int(revision) + 1
        self.assertEqual(session.query(
            f"UPDATE boards SET active_revision={next_revision}, canonical_state='{STATE}' "
            f"WHERE {SCOPE} AND active_revision={revision} AND policy_generation={policy} "
            f"AND active_lineage_id=X'{lineage}' AND lifecycle='active'; SELECT ROW_COUNT()"
        ), [b"1"])
        scope = f"'1',X'{BOARD}',X'{lineage}'"
        identity = f"'8',X'{OPERATION}'"
        session.query(
            f"INSERT INTO receipts VALUES ({scope},{identity},{next_revision},{policy},1,X'{digest}',1,"
            f"'{RECEIPT.decode('ascii')}')"
        )
        session.query(f"INSERT INTO accepted_events VALUES ({scope},{next_revision},{identity},1,'edit','{PAYLOAD}')")
        session.query(f"INSERT INTO outbox VALUES ({scope},{next_revision},'pending')")
        session.query(
            f"INSERT INTO audit_events VALUES (X'{AUDIT_ID}',1,'2026-01-01 00:00:00','board','1',"
            f"X'{BOARD}','user','8','edit','accepted','fixture',{policy},X'{OPERATION}')"
        )
        return RECEIPT

    def committed_view(self, baseline):
        new_rows = [
            f"audit\t1\t{BOARD}\t{AUDIT_ID}|1|board|user|8|edit|accepted|fixture|7|{OPERATION}",
            f"board\t1\t{BOARD}\t1|7|{LINEAGE}|{STATE}",
            f"event\t1\t{BOARD}\t{LINEAGE}|1|8|{OPERATION}|1|edit|{PAYLOAD}",
            f"outbox\t1\t{BOARD}\t{LINEAGE}|1|pending",
            f"receipt\t1\t{BOARD}\t{LINEAGE}|8|{OPERATION}|1|7|1|{fixture_digest(DEFAULT)}|1|"
            f"{RECEIPT.decode('ascii')}",
        ]
        self.assertEqual(len(baseline), 3)
        return sorted([*baseline[1:], *(row.encode("ascii") for row in new_rows)])

    def stage_policy_change(self, session):
        """Synthetic generation transition; not a runtime authority decision."""
        session.query("START TRANSACTION")
        self.assertEqual(session.query(HEAD_LOCK), [f"active\t{LINEAGE}\t1\t7".encode("ascii")])
        self.assertEqual(session.query(
            f"UPDATE boards SET policy_generation=8 WHERE {SCOPE} AND policy_generation=7; SELECT ROW_COUNT()"
        ), [b"1"])

    def generation_changed_view(self, rows):
        prefix = f"board\t1\t{BOARD}\t".encode("ascii")
        matching = [row for row in rows if row.startswith(prefix)]
        self.assertEqual(len(matching), 1)
        original, = matching
        fields = original[len(prefix):].split(b"|")
        self.assertEqual(fields[1], b"7")
        fields[1] = b"8"
        return sorted([row for row in rows if row != original] + [prefix + b"|".join(fields)])

    def wait_for_board_contention(self, observer, pending, waiter_id, blocker_id):
        """Require an engine-reported wait edge for these two owned sessions."""
        if "MariaDB" in self.engine_version:
            waits = "information_schema.INNODB_LOCK_WAITS"
            requester, blocker = "requesting_trx_id", "blocking_trx_id"
        else:
            waits = "performance_schema.data_lock_waits"
            requester, blocker = "REQUESTING_ENGINE_TRANSACTION_ID", "BLOCKING_ENGINE_TRANSACTION_ID"
        sql = (
            f"SELECT 1 FROM {waits} w "
            f"JOIN information_schema.INNODB_TRX r ON r.trx_id=w.{requester} "
            f"JOIN information_schema.INNODB_TRX b ON b.trx_id=w.{blocker} "
            "JOIN information_schema.PROCESSLIST p ON p.ID=r.trx_mysql_thread_id "
            f"WHERE r.trx_mysql_thread_id={waiter_id} AND b.trx_mysql_thread_id={blocker_id} "
            f"AND r.trx_state='LOCK WAIT' AND p.DB='{self.db}' "
            f"AND BINARY p.INFO=X'{HEAD_LOCK.encode('ascii').hex()}'"
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if observer.query(sql) == [b"1"]:
                self.assertFalse(pending.done())
                return
            if pending.done():
                pending.result()  # Surface a worker SQL/assertion failure first.
                self.fail("contender finished without the required scoped engine lock wait")
            # Poll pacing is not success evidence; only the native wait edge is.
            time.sleep(0.02)
        self.fail("no engine lock wait linking the contender to the owned board-fence holder")

    def test_generation_first_denies_waiting_old_generation_edit(self):
        with self.connection() as observer, self.connection() as policy, self.connection() as edit:
            baseline = observer.query(VIEW)
            changed = self.generation_changed_view(baseline)
            policy.query("START TRANSACTION")
            self.assertEqual(policy.query(HEAD_LOCK), [f"active\t{LINEAGE}\t0\t7".encode("ascii")])
            self.assertEqual(policy.query(
                f"UPDATE boards SET policy_generation=8 WHERE {SCOPE} AND policy_generation=7; SELECT ROW_COUNT()"
            ), [b"1"])
            self.assertEqual(policy.query(VIEW), changed)
            holder, = policy.query("SELECT CONNECTION_ID()")
            waiter, = edit.query("SELECT CONNECTION_ID()")
            edit.query("SET SESSION innodb_lock_wait_timeout=10")
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(self.stage, edit)
                try:
                    self.wait_for_board_contention(observer, pending, int(waiter), int(holder))
                    self.assertEqual(observer.query(VIEW), baseline)
                    policy.query("COMMIT")
                    self.assertEqual(pending.result(timeout=5), "POLICY_STALE")
                    self.assertEqual(edit.query(VIEW), changed)
                    edit.query("ROLLBACK")
                finally:
                    # Release the holder even if barrier/assertion checks fail.
                    # The worker's native lock timeout and Session's read timeout
                    # bound executor shutdown; context exits reap owned clients.
                    policy.query("ROLLBACK")
            self.assertEqual(observer.query(VIEW), changed)

    def test_write_first_preserves_acceptance_across_waiting_generation_change(self):
        with self.connection() as observer, self.connection() as edit, self.connection() as policy:
            baseline = observer.query(VIEW)
            committed = self.committed_view(baseline)
            changed = self.generation_changed_view(committed)
            self.assertEqual(self.stage(edit), RECEIPT)
            holder, = edit.query("SELECT CONNECTION_ID()")
            waiter, = policy.query("SELECT CONNECTION_ID()")
            policy.query("SET SESSION innodb_lock_wait_timeout=10")
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(self.stage_policy_change, policy)
                try:
                    self.wait_for_board_contention(observer, pending, int(waiter), int(holder))
                    self.assertEqual(edit.query(VIEW), committed)
                    self.assertEqual(observer.query(VIEW), baseline)
                    edit.query("COMMIT")
                    pending.result(timeout=5)
                    self.assertEqual(observer.query(VIEW), committed)
                    self.assertEqual(policy.query(VIEW), changed)
                    policy.query("COMMIT")
                finally:
                    edit.query("ROLLBACK")
            self.assertEqual(observer.query(VIEW), changed)

            with self.connection() as retry:
                # Keep the original identity, digest and generation-7 preconditions.
                # Current synthetic read permission alone permits receipt recovery.
                self.assertEqual(self.stage(retry, replace(DEFAULT, write_allowed=False)), RECEIPT)
                self.assertEqual(retry.query(VIEW), changed)
                retry.query("ROLLBACK")
                self.assertEqual(self.stage(retry, replace(DEFAULT, payload="changed edit")), "IDEMPOTENCY_CONFLICT")
                retry.query("ROLLBACK")
                self.assertEqual(self.stage(retry, replace(DEFAULT, read_allowed=False)), "CONCEALED")
                self.assertEqual(retry.query(VIEW), changed)
            self.assertEqual(observer.query(VIEW), changed)

    def test_commit_visibility_and_retry_after_discarded_result(self):
        with self.connection() as observer, self.connection() as owner:
            baseline = observer.query(VIEW)
            connection_id = owner.query("SELECT CONNECTION_ID()")
            self.assertNotEqual(connection_id, observer.query("SELECT CONNECTION_ID()"))
            self.stage(owner)  # Deliberately discard the local operation result.
            committed = self.committed_view(baseline)
            self.assertEqual(owner.query(VIEW), committed)
            self.assertEqual(observer.query(VIEW), baseline)
            owner.query("COMMIT")
            self.assertEqual(owner.query("SELECT CONNECTION_ID()"), connection_id)
            self.assertEqual(observer.query(VIEW), committed)

        with self.connection() as retry:
            self.assertNotEqual(retry.query("SELECT CONNECTION_ID()"), connection_id)
            self.assertEqual(self.stage(retry, replace(DEFAULT, write_allowed=False)), RECEIPT)
            retry.query("ROLLBACK")
            self.assertEqual(self.stage(retry, replace(DEFAULT, payload="changed edit")), "IDEMPOTENCY_CONFLICT")
            retry.query("ROLLBACK")
            self.assertEqual(self.stage(retry, replace(DEFAULT, read_allowed=False)), "CONCEALED")
            self.assertEqual(retry.query(VIEW), committed)

    def test_denial_and_staleness_leave_every_collection_unchanged(self):
        cases = (
            (replace(DEFAULT, shape_valid=False), "INVALID_SHAPE"),
            (replace(DEFAULT, read_allowed=False), "CONCEALED"),
            (replace(DEFAULT, write_allowed=False), "CONCEALED"),
            (replace(DEFAULT, actor="9"), "CONCEALED"),
            (replace(DEFAULT, guild="2"), "CONCEALED"),
            (replace(DEFAULT, board=OTHER_BOARD), "CONCEALED"),
            (replace(DEFAULT, lineage="77" * 16), "LINEAGE_CHANGED"),
            (replace(DEFAULT, policy=6), "POLICY_STALE"),
            (replace(DEFAULT, base=1), "CONFLICT"),
        )
        with self.connection() as observer, self.connection() as owner:
            baseline = observer.query(VIEW)
            for attempt, outcome in cases:
                with self.subTest(attempt=attempt):
                    self.assertEqual(self.stage(owner, attempt), outcome)
                    self.assertEqual(owner.query(VIEW), baseline)
                    owner.query("ROLLBACK")
                    self.assertEqual(observer.query(VIEW), baseline)

    def test_explicit_rollback_and_failed_session_preserve_baseline(self):
        with self.connection() as observer:
            baseline = observer.query(VIEW)
            with self.connection() as owner:
                self.assertEqual(self.stage(owner), RECEIPT)
                self.assertEqual(owner.query(VIEW), self.committed_view(baseline))
                owner.query("ROLLBACK")
                self.assertEqual(observer.query(VIEW), baseline)
            with self.connection() as owner:
                self.assertEqual(self.stage(owner), RECEIPT)
                self.assertEqual(owner.query(VIEW), self.committed_view(baseline))
                self.assertEqual(observer.query(VIEW), baseline)
                # The audit ID we just read duplicates the primary key.
                with self.assertRaisesRegex(SCHEMA.Fenced, "SQL statement failed or session ended"):
                    owner.query(f"INSERT INTO audit_events SELECT * FROM audit_events WHERE event_id=X'{AUDIT_ID}'")
                self.assertNotEqual(owner.client.wait(timeout=5), 0)
            self.assertEqual(observer.query(VIEW), baseline)
            with self.connection() as retry:
                self.assertEqual(self.stage(retry), RECEIPT)
                retry.query("COMMIT")
            self.assertEqual(observer.query(VIEW), self.committed_view(baseline))

    def test_concurrent_duplicate_waits_then_reads_committed_receipt(self):
        with self.connection() as observer, self.connection() as owner, self.connection() as contender:
            baseline = observer.query(VIEW)
            self.assertEqual(self.stage(owner), RECEIPT)
            connection_id, = contender.query("SELECT CONNECTION_ID()")
            contender.query("SET SESSION innodb_lock_wait_timeout=10")
            with ThreadPoolExecutor(max_workers=1) as executor:
                duplicate = executor.submit(self.stage, contender)
                try:
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        current = observer.query(
                            "SELECT INFO FROM information_schema.PROCESSLIST "
                            f"WHERE ID={int(connection_id)}"
                        )
                        if current == [HEAD_LOCK.encode("ascii")]:
                            break
                        if duplicate.done():
                            self.fail("contender finished before reaching the scoped board lock")
                        time.sleep(0.02)
                    else:
                        self.fail("contender did not appear at the scoped board lock")
                    self.assertFalse(duplicate.done())
                    self.assertEqual(observer.query(VIEW), baseline)
                    owner.query("COMMIT")
                    self.assertEqual(duplicate.result(timeout=5), RECEIPT)
                    contender.query("ROLLBACK")
                finally:
                    owner.query("ROLLBACK")
            self.assertEqual(observer.query(VIEW), self.committed_view(baseline))

    def test_lock_timeout_leaves_baseline_and_allows_same_identity_retry(self):
        with self.connection() as observer, self.connection() as owner:
            baseline = observer.query(VIEW)
            self.assertEqual(self.stage(owner), RECEIPT)
            result = subprocess.run(
                [*self.cli, f"--database={self.db}", "-e",
                 f"SET SESSION innodb_lock_wait_timeout=1; START TRANSACTION; {HEAD_LOCK}"],
                capture_output=True, text=True, timeout=5,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertRegex(result.stderr, r"ERROR 1205\b")
            self.assertEqual(result.stdout, "")
            self.assertEqual(observer.query(VIEW), baseline)
            owner.query("ROLLBACK")

            with self.connection() as retry:
                self.assertEqual(self.stage(retry), RECEIPT)
                retry.query("COMMIT")
            self.assertEqual(observer.query(VIEW), self.committed_view(baseline))
