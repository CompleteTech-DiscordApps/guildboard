import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "database/verify_initial_schema.py"
SPEC = importlib.util.spec_from_file_location("initial_schema", TOOL)
SCHEMA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCHEMA)
GENERATION = "a" * 32
DDL = SCHEMA.statements(SCHEMA.SOURCE.read_bytes())


class MigrationSourceTests(unittest.TestCase):
    def test_manifest_covers_ordered_source(self):
        self.assertEqual(SCHEMA.sha(SCHEMA.SOURCE.read_bytes()), SCHEMA.SOURCE_DIGEST)
        for manifest in SCHEMA.CATALOG.values():
            self.assertEqual(len(DDL), len(manifest))
            self.assertTrue(all(re.fullmatch("[0-9A-F]{64}", entry) for entry in manifest))


@unittest.skipUnless(
    all(os.environ.get(name) for name in ("GB_SCHEMA_CLIENT", "GB_SCHEMA_SOCKET", "GB_SCHEMA_USER")),
    "requires explicit disposable, privately configured SQL fixture",
)
class EngineTests(unittest.TestCase):
    def setUp(self):
        client = Path(os.environ["GB_SCHEMA_CLIENT"])
        socket = Path(os.environ["GB_SCHEMA_SOCKET"])
        user = os.environ["GB_SCHEMA_USER"]
        self.assertTrue(client.is_absolute() and socket.is_absolute() and socket.is_socket())
        self.assertNotIn("MYSQL_PWD", os.environ)
        self.db = "gb148_" + uuid.uuid4().hex
        self.cli = [str(client), "--no-defaults"]
        if client.name == "mysql":
            self.cli.append("--no-login-paths")
        self.cli.extend([
            "--protocol=socket", f"--socket={socket}", f"--user={user}",
            "--batch", "--skip-column-names", "--unbuffered", "--skip-reconnect", "--binary-mode",
        ])
        self.tool = [
            sys.executable, "-B", str(TOOL), "--client", str(client), "--socket", str(socket),
            "--user", user, "--database", self.db,
        ]
        actual = self.sql(
            "SELECT VERSION(), @@global.skip_networking", use_database=False
        ).split("\t")
        self.assertIn(actual[0], SCHEMA.CATALOG)
        self.assertEqual(actual[1], "1")
        self.sql(f"CREATE DATABASE {self.db}", use_database=False)
        # The database name was generated and created by this test.
        self.addCleanup(self.sql, f"DROP DATABASE {self.db}", use_database=False)

    def sql(self, sql, error=None, use_database=True):
        db_arg = [f"--database={self.db}"] if use_database else []
        result = subprocess.run(
            [*self.cli, *db_arg, "-e", "SET NAMES ascii COLLATE ascii_bin; " + sql], text=True, capture_output=True, timeout=15
        )
        if error:
            self.assertNotEqual(result.returncode, 0)
            self.assertRegex(result.stderr, rf"ERROR ({error})\b")
        else:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def verify(self, apply=False, generation=GENERATION, error=None):
        result = subprocess.run(
            [*self.tool, "--generation", generation, *(["--apply"] if apply else [])],
            text=True, capture_output=True, timeout=60,
        )
        if error:
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(error, result.stderr)
        else:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "schema v1 activated and verified")

    def seed_progress(self, completed, actual):
        for ddl in DDL[:actual]:
            self.sql(ddl)
        digest = SCHEMA.SOURCE_DIGEST
        self.sql(
            "INSERT INTO schema_installation VALUES "
            f"(1,1,0,1,X'{digest}',X'{GENERATION}','schema-v1',5,{completed},'planned')"
        )

    def test_clean_install_verifies_with_noop_retry(self):
        self.verify(error="not activated")
        self.verify(apply=True)
        self.verify()
        self.verify(apply=True)
        self.assertEqual(
            self.sql("SELECT owner_epoch, completed_steps, phase FROM schema_installation"),
            f"1\t{len(DDL)}\tactivated",
        )
        self.verify(apply=True, generation="b" * 32, error="identity, generation")
        self.sql("UPDATE schema_installation SET migration_digest=REPEAT('x',32)")
        self.verify(apply=True, error="identity, generation")

    def test_read_only_principal_cannot_install_schema(self):
        observer = "gbro_" + uuid.uuid4().hex[:20]
        account = f"'{observer}'@'localhost'"
        self.sql(f"CREATE USER {account}", use_database=False)
        self.addCleanup(self.sql, f"DROP USER {account}", use_database=False)
        self.sql(f"GRANT SELECT ON `{self.db}`.* TO {account}", use_database=False)

        denied = list(self.tool)
        denied[denied.index("--user") + 1] = observer
        result = subprocess.run(
            [*denied, "--generation", GENERATION, "--apply"],
            text=True, capture_output=True, timeout=60,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("schema fenced", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.sql("SHOW TABLES"), "")

    def test_interrupted_alter_resumes_exactly_one_unjournaled_step(self):
        # End the owner session immediately after the implicit DDL commit,
        # deliberately leaving the previous journal count.
        self.seed_progress(completed=6, actual=6)
        with SCHEMA.Session([*self.cli, f"--database={self.db}"], self.db) as owner:
            SCHEMA.preflight(owner)
            self.assertEqual(owner.query("SELECT GET_LOCK(CONCAT('gb.v1:', SHA2(DATABASE(),224)),0)"), [b"1"])
            owner.query(DDL[6])
            self.verify(apply=True, error="already owned")
            owner.client.kill()
            owner.client.wait(timeout=5)

        self.verify(error="unsupported migration phase")
        self.verify(apply=True)
        self.assertEqual(
            self.sql("SELECT owner_epoch, completed_steps, phase FROM schema_installation"),
            f"6\t{len(DDL)}\tactivated",
        )

    def test_fenced_catalog_and_nonempty_resume_make_no_progress(self):
        self.seed_progress(completed=2, actual=2)
        self.sql("INSERT INTO guilds VALUES ('1','active')")
        self.verify(apply=True, error="unexpected application data")
        self.assertEqual(self.sql("SELECT lifecycle FROM guilds WHERE guild_id='1'"), "active")
        self.sql("ALTER TABLE guilds DROP COLUMN lifecycle")
        self.verify(apply=True, error="catalog differs")
        self.assertEqual(self.sql("SELECT owner_epoch, completed_steps FROM schema_installation"), "5\t2")

    def test_exhausted_epoch_fails_closed(self):
        self.seed_progress(completed=1, actual=1)
        self.sql("UPDATE schema_installation SET owner_epoch=18446744073709551615")
        self.verify(apply=True, error="exhausted owner fence")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()"), "1")

    def test_scoped_references_and_retained_receipt(self):
        self.verify(apply=True)
        board, other, lineage, wrong, receipt, proof, foreign = [
            f"UNHEX(REPEAT('{x}',32))" for x in "1234567"
        ]
        self.sql(
            "INSERT INTO guilds VALUES ('1','active'),('2','active'); "
            "INSERT INTO boards (guild_id,board_id,name,lifecycle,active_revision,policy_generation,"
            "state_codec,canonical_state) VALUES "
            f"('1',{board},'a','initializing',0,0,1,'x'), ('2',{foreign},'b','initializing',0,0,1,'y'), "
            f"('1',{other},'c','initializing',0,0,1,'z'); "
            "INSERT INTO lineages (guild_id,board_id,lineage_id,origin,initial_revision) VALUES "
            f"('1',{board},{lineage},'creation',0), ('2',{foreign},{lineage},'creation',0), "
            f"('1',{other},{wrong},'creation',0); "
            "INSERT INTO receipt_coverage VALUES "
            f"('1',{board},0,{proof},{lineage},0,'proof'); "
            f"UPDATE boards SET lifecycle='active', active_lineage_id={lineage}, recovery_generation=0,"
            f"coverage_proof_id={proof} WHERE guild_id='1' AND board_id={board}; "
            f"INSERT INTO channel_defaults VALUES ('1','9',{board});"
        )
        self.sql(f"INSERT INTO channel_defaults VALUES ('1','8',{foreign})", error="1452")
        self.assertEqual(self.sql(f"SELECT lifecycle FROM boards WHERE guild_id='1' AND board_id={board}"), "active")
        self.sql(f"UPDATE boards SET active_lineage_id={wrong} WHERE guild_id='1' AND board_id={board}", error="1452")
        self.sql(
            f"INSERT INTO deletion_jobs VALUES ('1',{proof},1,'board',{foreign},NULL,'fenced',NULL)",
            error="1452",
        )
        self.sql(
            f"INSERT INTO deletion_jobs VALUES ('1',{proof},1,'subject',{board},'7','fenced',NULL)",
            error="3819|4025",
        )
        counter = 2**64 - 1
        fields = f"'1',{board},{lineage}"
        self.sql(
            "START TRANSACTION; "
            f"INSERT INTO receipts VALUES ({fields},'8',{receipt},{counter},{counter},1,REPEAT('a',32),1,'accepted'); "
            f"INSERT INTO accepted_events VALUES ({fields},{counter},'8',{receipt},1,'edit','payload'); "
            f"INSERT INTO outbox VALUES ({fields},{counter},'pending'); COMMIT"
        )
        self.sql("DELETE FROM accepted_events", error="1451")
        self.sql("DELETE FROM outbox; DELETE FROM accepted_events")
        self.verify(apply=True)
        self.assertEqual(
            self.sql("SELECT revision, policy_generation, canonical_receipt FROM receipts"),
            f"{counter}\t{counter}\taccepted",
        )
        self.assertEqual(self.sql("SELECT COUNT(*) FROM channel_defaults"), "1")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM deletion_jobs"), "0")

    def test_activated_catalog_drift_fences_reentry(self):
        self.verify(apply=True)
        self.sql("ALTER TABLE channel_defaults DROP FOREIGN KEY fk_default_board")
        self.verify(error="catalog differs")
        self.verify(apply=True, error="catalog differs")
