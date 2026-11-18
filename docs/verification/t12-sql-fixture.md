# T12 opt-in SQL fixture

Related #392 / `GB-T12.01.01.T1`. This bounded fixture complements the
[offline harness](t12-harness.md) under the accepted
[T12 evidence contract](../specifications/GB-T12-S1-verification-evidence-contract.md)
and [T5 migration contract](../../database/README.md). It does not close #392.

A separately authorized caller must supply an already disposable local engine,
a verified absolute `mysql` or `mariadb` executable, an absolute Unix socket in
an effective-UID-owned mode-0700 directory, and a fixture administrator account.
The executable must be a regular executable file owned by root or the effective
UID, without group/other write permission. Symlink/noncanonical paths are rejected.
These checks cannot establish binary provenance or whether data is disposable;
`disposable=True` is the caller's explicit target authorization. Never point this
fixture at an existing shared or production engine. It neither starts a daemon
nor discovers credentials, sockets, clients or targets from the environment.

Use synchronously on POSIX in the main thread, with cooperative exclusive
ownership of the private socket directory and engine throughout the context:

```python
from pathlib import Path
from scripts.verification.t12_sql_fixture import SqlFixtureConfig, sql_fixture_run

config = SqlFixtureConfig(
    client=Path("/owned-fixture/bin/mysql"),
    socket=Path("/owned-fixture/private/mysql.sock"),
    admin_user="fixture_admin", disposable=True,
)
with sql_fixture_run(config) as run:
    with run.writer() as writer, run.observer() as observer:
        rows = observer.query("SELECT phase FROM schema_installation WHERE singleton=1")
```

Only trusted local test SQL may reach these sessions. The writer uses the fixture
administrator; it is not an application writer grant contract. The observer has
a generated distinct `localhost` principal granted only `SELECT` on this run's
database and uses its own client process/connection. Callers seed accepted scoped
rows through existing domain fixtures and independently observe their results;
this helper invents no auth, policy, API, storage, bot or transaction interface.

Children have an empty environment, `--no-defaults`, MySQL `--no-login-paths`,
explicit socket/user/database, disabled reconnect and a one-second connect
limit. No password argument or ambient credential file is used. Each connection
checks the exact supported engine identity and `skip_networking=1`; the accepted
migration performs its additional database/session, source-digest, catalog and
activation checks. Supported versions are exactly the separate manifests in
`database/verify_initial_schema.py`: MySQL 8.4.11 and MariaDB
11.4.13-MariaDB-ubu2404. No other version is inferred compatible.

Each run generates a database, observer name and independent 128-bit migration
generation. It invokes `verify_initial_schema.migration(..., apply=True)` directly.
No `IF NOT EXISTS`, retry, broad deletion or caller-selected database is used.
Only acknowledged successful creates enter the owned inventory. A failed or
cancelled CREATE is unknown and is preserved, even if the engine may have
committed it. Exceptions expose a local `inventory` tuple of resource kind,
synthetic name and ownership state for authorized reconciliation. Migration
failure remains unknown/fenced; it does not produce a usable fixture.

Run/query deadlines use monotonic time. Defaults are 30 seconds overall,
3 seconds per query and a shared 5-second SQL cleanup deadline, bounded to
60/10/10 seconds. Each query admits at most 64 KiB input/output and each session
1024 queries. A run permits at most 32 connections and four concurrently active
connections. Timed-out, interrupted or incomplete query sessions become unusable.
Client teardown kills/reaps only its tracked child, with at most 0.5 seconds per
child; this bounded reap allowance supplements the SQL deadline. SIGINT is deferred
across acquisition until its child is registered. Catchable interruption closes
sessions and attempts cleanup; repeated cancellation, default SIGTERM, SIGKILL,
host loss and same-UID/privileged target replacement require owner reconciliation.

Cleanup stops new work, drops only acknowledged owned resources, checks their
absence through fresh administrator connections and attempts the remaining
resource even if one cleanup fails. It never automatically deletes an uncertain
CREATE. Failure or uncertainty blocks acceptance. Do not reuse or publish data
from a failed run. Privileged concurrent replacement of an owned SQL object is
outside the cooperative ownership assumption. A consuming real-engine run must
separately observe an unrelated sentinel before and after execution.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests/verification -p test_t12_sql_fixture.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -B -O -m unittest discover -s tests/verification -p test_t12_sql_fixture.py -v
```

The tests use synthetic SQL ports and synthetic socket metadata; no socket is
bound or contacted. Isolated Python children exercise the actual bounded client
I/O seam. Migration invocation, observer identity/grants, scope isolation,
configuration zero effects, sentinel preservation, failures, cancellation and
unknown cleanup are fixture-class observations. No supported engine binary is
available in this environment. Historical schema evidence is not refreshed by
these tests. Fresh real-engine installation, observer privilege denial and
independent catalog/sentinel checks remain pending, along with functional,
security and consumer review and #393 verification. The existing full harness
`integration` target remains fail-closed for unavailable SQL/API/auth, policy,
storage and bot prerequisites and the unresolved T1/T2/T4 runtime blockers.
