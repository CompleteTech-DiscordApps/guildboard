-- GB-T5.S1 v1. Ordered DDL consumed by database/verify_initial_schema.py.
-- Each statement autocommits. Use the verifier to install and resume.

CREATE TABLE schema_installation (
    singleton TINYINT UNSIGNED NOT NULL PRIMARY KEY,
    migration_id SMALLINT UNSIGNED NOT NULL,
    source_version SMALLINT UNSIGNED NOT NULL,
    target_version SMALLINT UNSIGNED NOT NULL,
    migration_digest BINARY(32) NOT NULL,
    storage_generation BINARY(16) NOT NULL,
    compatible_binary_set VARBINARY(32) NOT NULL,
    owner_epoch BIGINT UNSIGNED NOT NULL,
    completed_steps SMALLINT UNSIGNED NOT NULL,
    phase ENUM('planned','expanded','backfilled','verified','activated','contracted') NOT NULL,
    CONSTRAINT ck_schema_singleton CHECK (singleton = 1)
) ENGINE=InnoDB DEFAULT CHARSET=ascii COLLATE=ascii_bin;

CREATE TABLE guilds (
    guild_id VARBINARY(20) NOT NULL PRIMARY KEY,
    lifecycle ENUM('active','deletion_fenced') NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=ascii COLLATE=ascii_bin;

CREATE TABLE boards (
    guild_id VARBINARY(20) NOT NULL,
    board_id BINARY(16) NOT NULL,
    name VARBINARY(255) NOT NULL,
    lifecycle ENUM('initializing','active','archived','deletion_fenced') NOT NULL,
    active_lineage_id BINARY(16) NULL,
    active_revision BIGINT UNSIGNED NOT NULL,
    policy_generation BIGINT UNSIGNED NOT NULL,
    state_codec SMALLINT UNSIGNED NOT NULL,
    canonical_state LONGBLOB NOT NULL,
    PRIMARY KEY (guild_id, board_id),
    KEY ix_board_lifecycle (guild_id, lifecycle, board_id),
    CONSTRAINT fk_board_guild FOREIGN KEY (guild_id) REFERENCES guilds (guild_id),
    CONSTRAINT ck_board_codec CHECK (state_codec = 1),
    CONSTRAINT ck_board_head CHECK (
        (lifecycle = 'initializing' AND active_lineage_id IS NULL AND active_revision = 0)
        OR (lifecycle <> 'initializing' AND active_lineage_id IS NOT NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=ascii COLLATE=ascii_bin;

CREATE TABLE channel_defaults (
    guild_id VARBINARY(20) NOT NULL,
    channel_id VARBINARY(20) NOT NULL,
    board_id BINARY(16) NOT NULL,
    PRIMARY KEY (guild_id, channel_id),
    KEY ix_default_board (guild_id, board_id, channel_id),
    CONSTRAINT fk_default_board FOREIGN KEY (guild_id, board_id) REFERENCES boards (guild_id, board_id)
) ENGINE=InnoDB DEFAULT CHARSET=ascii COLLATE=ascii_bin;

CREATE TABLE board_policy_rules (
    guild_id VARBINARY(20) NOT NULL,
    board_id BINARY(16) NOT NULL,
    subject_kind ENUM('user','role','everyone') NOT NULL,
    subject_ref VARBINARY(20) NOT NULL,
    rule_id BINARY(16) NOT NULL,
    rule_version SMALLINT UNSIGNED NOT NULL,
    canonical_rule BLOB NOT NULL,
    expires_at_utc DATETIME(6) NULL,
    PRIMARY KEY (guild_id, board_id, subject_kind, subject_ref, rule_id),
    CONSTRAINT fk_rule_board FOREIGN KEY (guild_id, board_id) REFERENCES boards (guild_id, board_id),
    CONSTRAINT ck_rule_version CHECK (rule_version = 1)
) ENGINE=InnoDB DEFAULT CHARSET=ascii COLLATE=ascii_bin;

CREATE TABLE lineages (
    guild_id VARBINARY(20) NOT NULL,
    board_id BINARY(16) NOT NULL,
    lineage_id BINARY(16) NOT NULL,
    origin ENUM('creation','document_restore','disaster_promotion') NOT NULL,
    parent_lineage_id BINARY(16) NULL,
    source_lineage_id BINARY(16) NULL,
    source_snapshot_id BINARY(16) NULL,
    initial_revision BIGINT UNSIGNED NOT NULL,
    final_revision BIGINT UNSIGNED NULL,
    PRIMARY KEY (guild_id, board_id, lineage_id),
    KEY ix_lineage_parent (guild_id, board_id, parent_lineage_id),
    KEY ix_lineage_source (guild_id, board_id, source_lineage_id, source_snapshot_id),
    CONSTRAINT fk_lineage_board FOREIGN KEY (guild_id, board_id) REFERENCES boards (guild_id, board_id),
    CONSTRAINT fk_lineage_parent FOREIGN KEY (guild_id, board_id, parent_lineage_id)
        REFERENCES lineages (guild_id, board_id, lineage_id),
    CONSTRAINT ck_lineage_cut CHECK (final_revision IS NULL OR final_revision >= initial_revision),
    CONSTRAINT ck_lineage_source CHECK (
        (source_lineage_id IS NULL AND source_snapshot_id IS NULL AND origin <> 'document_restore')
        OR (source_lineage_id IS NOT NULL AND source_snapshot_id IS NOT NULL AND origin <> 'creation')
    ),
    CONSTRAINT ck_lineage_parent CHECK (
        (origin <> 'creation' OR parent_lineage_id IS NULL)
        AND (origin <> 'document_restore' OR parent_lineage_id IS NOT NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=ascii COLLATE=ascii_bin;

ALTER TABLE boards ADD CONSTRAINT fk_board_head FOREIGN KEY (guild_id, board_id, active_lineage_id)
    REFERENCES lineages (guild_id, board_id, lineage_id);

CREATE TABLE receipt_coverage (
    guild_id VARBINARY(20) NOT NULL,
    board_id BINARY(16) NOT NULL,
    recovery_generation BIGINT UNSIGNED NOT NULL,
    proof_id BINARY(16) NOT NULL,
    cut_lineage_id BINARY(16) NOT NULL,
    cut_revision BIGINT UNSIGNED NOT NULL,
    provenance BLOB NOT NULL,
    PRIMARY KEY (guild_id, board_id, recovery_generation, proof_id),
    CONSTRAINT fk_coverage_cut FOREIGN KEY (guild_id, board_id, cut_lineage_id)
        REFERENCES lineages (guild_id, board_id, lineage_id)
) ENGINE=InnoDB DEFAULT CHARSET=ascii COLLATE=ascii_bin;

CREATE TABLE receipt_coverage_lineages (
    guild_id VARBINARY(20) NOT NULL,
    board_id BINARY(16) NOT NULL,
    recovery_generation BIGINT UNSIGNED NOT NULL,
    proof_id BINARY(16) NOT NULL,
    lineage_id BINARY(16) NOT NULL,
    PRIMARY KEY (guild_id, board_id, recovery_generation, proof_id, lineage_id),
    CONSTRAINT fk_complete_proof FOREIGN KEY (guild_id, board_id, recovery_generation, proof_id)
        REFERENCES receipt_coverage (guild_id, board_id, recovery_generation, proof_id),
    CONSTRAINT fk_complete_lineage FOREIGN KEY (guild_id, board_id, lineage_id)
        REFERENCES lineages (guild_id, board_id, lineage_id)
) ENGINE=InnoDB DEFAULT CHARSET=ascii COLLATE=ascii_bin;

ALTER TABLE boards
    ADD COLUMN recovery_generation BIGINT UNSIGNED NULL,
    ADD COLUMN coverage_proof_id BINARY(16) NULL,
    ADD CONSTRAINT ck_board_coverage CHECK (
        (lifecycle = 'initializing' AND recovery_generation IS NULL AND coverage_proof_id IS NULL)
        OR (lifecycle <> 'initializing' AND recovery_generation IS NOT NULL AND coverage_proof_id IS NOT NULL)
    ),
    ADD CONSTRAINT fk_board_coverage FOREIGN KEY (guild_id, board_id, recovery_generation, coverage_proof_id)
        REFERENCES receipt_coverage (guild_id, board_id, recovery_generation, proof_id);

CREATE TABLE receipts (
    guild_id VARBINARY(20) NOT NULL,
    board_id BINARY(16) NOT NULL,
    lineage_id BINARY(16) NOT NULL,
    actor_user_id VARBINARY(20) NOT NULL,
    operation_id BINARY(16) NOT NULL,
    revision BIGINT UNSIGNED NOT NULL,
    policy_generation BIGINT UNSIGNED NOT NULL,
    digest_codec SMALLINT UNSIGNED NOT NULL,
    semantic_digest BINARY(32) NOT NULL,
    receipt_version SMALLINT UNSIGNED NOT NULL,
    canonical_receipt BLOB NOT NULL,
    PRIMARY KEY (guild_id, board_id, lineage_id, actor_user_id, operation_id),
    UNIQUE KEY uq_receipt_revision (guild_id, board_id, lineage_id, revision),
    UNIQUE KEY uq_receipt_event (guild_id, board_id, lineage_id, actor_user_id, operation_id, revision),
    CONSTRAINT fk_receipt_lineage FOREIGN KEY (guild_id, board_id, lineage_id)
        REFERENCES lineages (guild_id, board_id, lineage_id),
    CONSTRAINT ck_receipt_version CHECK (receipt_version = 1 AND digest_codec = 1 AND revision > 0)
) ENGINE=InnoDB DEFAULT CHARSET=ascii COLLATE=ascii_bin;

CREATE TABLE accepted_events (
    guild_id VARBINARY(20) NOT NULL,
    board_id BINARY(16) NOT NULL,
    lineage_id BINARY(16) NOT NULL,
    revision BIGINT UNSIGNED NOT NULL,
    actor_user_id VARBINARY(20) NOT NULL,
    operation_id BINARY(16) NOT NULL,
    event_version SMALLINT UNSIGNED NOT NULL,
    kind VARBINARY(64) NOT NULL,
    canonical_payload BLOB NOT NULL,
    PRIMARY KEY (guild_id, board_id, lineage_id, revision),
    CONSTRAINT fk_event_lineage FOREIGN KEY (guild_id, board_id, lineage_id)
        REFERENCES lineages (guild_id, board_id, lineage_id),
    CONSTRAINT fk_event_receipt FOREIGN KEY (guild_id, board_id, lineage_id, actor_user_id, operation_id, revision)
        REFERENCES receipts (guild_id, board_id, lineage_id, actor_user_id, operation_id, revision),
    CONSTRAINT ck_event_version CHECK (event_version = 1 AND revision > 0)
) ENGINE=InnoDB DEFAULT CHARSET=ascii COLLATE=ascii_bin;

CREATE TABLE outbox (
    guild_id VARBINARY(20) NOT NULL,
    board_id BINARY(16) NOT NULL,
    lineage_id BINARY(16) NOT NULL,
    revision BIGINT UNSIGNED NOT NULL,
    delivery_state ENUM('pending','delivered') NOT NULL,
    PRIMARY KEY (guild_id, board_id, lineage_id, revision),
    KEY ix_outbox_scan (delivery_state, guild_id, board_id, lineage_id, revision),
    CONSTRAINT fk_outbox_event FOREIGN KEY (guild_id, board_id, lineage_id, revision)
        REFERENCES accepted_events (guild_id, board_id, lineage_id, revision)
) ENGINE=InnoDB DEFAULT CHARSET=ascii COLLATE=ascii_bin;

CREATE TABLE snapshots (
    guild_id VARBINARY(20) NOT NULL,
    board_id BINARY(16) NOT NULL,
    lineage_id BINARY(16) NOT NULL,
    snapshot_id BINARY(16) NOT NULL,
    cut_revision BIGINT UNSIGNED NOT NULL,
    format_version SMALLINT UNSIGNED NOT NULL,
    state_codec SMALLINT UNSIGNED NOT NULL,
    canonical_digest BINARY(32) NOT NULL,
    byte_length BIGINT UNSIGNED NOT NULL,
    object_ref BINARY(16) NOT NULL,
    asset_manifest_digest BINARY(32) NOT NULL,
    applied_deletion_cut BIGINT UNSIGNED NULL,
    deletion_proof_ref BINARY(16) NULL,
    checkpoint_label VARBINARY(255) NULL,
    checkpoint_actor VARBINARY(20) NULL,
    PRIMARY KEY (guild_id, board_id, lineage_id, snapshot_id),
    KEY ix_snapshot_cut (guild_id, board_id, lineage_id, cut_revision, snapshot_id),
    CONSTRAINT fk_snapshot_lineage FOREIGN KEY (guild_id, board_id, lineage_id)
        REFERENCES lineages (guild_id, board_id, lineage_id),
    CONSTRAINT ck_snapshot_version CHECK (format_version = 1 AND state_codec = 1 AND byte_length > 0),
    CONSTRAINT ck_snapshot_proof CHECK ((applied_deletion_cut IS NULL) = (deletion_proof_ref IS NULL)),
    CONSTRAINT ck_snapshot_label CHECK ((checkpoint_label IS NULL) = (checkpoint_actor IS NULL))
) ENGINE=InnoDB DEFAULT CHARSET=ascii COLLATE=ascii_bin;

ALTER TABLE lineages ADD CONSTRAINT fk_lineage_snapshot
    FOREIGN KEY (guild_id, board_id, source_lineage_id, source_snapshot_id)
    REFERENCES snapshots (guild_id, board_id, lineage_id, snapshot_id);

CREATE TABLE assets (
    guild_id VARBINARY(20) NOT NULL,
    board_id BINARY(16) NOT NULL,
    asset_id BINARY(16) NOT NULL,
    content_type VARBINARY(64) NOT NULL,
    canonical_digest BINARY(32) NOT NULL,
    byte_length BIGINT UNSIGNED NOT NULL,
    object_ref BINARY(16) NOT NULL,
    PRIMARY KEY (guild_id, board_id, asset_id),
    UNIQUE KEY uq_asset_object (guild_id, board_id, object_ref),
    CONSTRAINT fk_asset_board FOREIGN KEY (guild_id, board_id) REFERENCES boards (guild_id, board_id),
    CONSTRAINT ck_asset_bytes CHECK (byte_length > 0)
) ENGINE=InnoDB DEFAULT CHARSET=ascii COLLATE=ascii_bin;

CREATE TABLE snapshot_assets (
    guild_id VARBINARY(20) NOT NULL,
    board_id BINARY(16) NOT NULL,
    lineage_id BINARY(16) NOT NULL,
    snapshot_id BINARY(16) NOT NULL,
    asset_id BINARY(16) NOT NULL,
    PRIMARY KEY (guild_id, board_id, lineage_id, snapshot_id, asset_id),
    KEY ix_snap_asset_reach (guild_id, board_id, asset_id, lineage_id, snapshot_id),
    CONSTRAINT fk_snap_asset_snapshot FOREIGN KEY (guild_id, board_id, lineage_id, snapshot_id)
        REFERENCES snapshots (guild_id, board_id, lineage_id, snapshot_id),
    CONSTRAINT fk_snap_asset_asset FOREIGN KEY (guild_id, board_id, asset_id)
        REFERENCES assets (guild_id, board_id, asset_id)
) ENGINE=InnoDB DEFAULT CHARSET=ascii COLLATE=ascii_bin;

CREATE TABLE asset_pins (
    guild_id VARBINARY(20) NOT NULL,
    board_id BINARY(16) NOT NULL,
    asset_id BINARY(16) NOT NULL,
    pin_id BINARY(16) NOT NULL,
    lineage_id BINARY(16) NOT NULL,
    cut_revision BIGINT UNSIGNED NOT NULL,
    owner_ref BINARY(16) NOT NULL,
    PRIMARY KEY (guild_id, board_id, asset_id, pin_id),
    CONSTRAINT fk_pin_asset FOREIGN KEY (guild_id, board_id, asset_id)
        REFERENCES assets (guild_id, board_id, asset_id),
    CONSTRAINT fk_pin_lineage FOREIGN KEY (guild_id, board_id, lineage_id)
        REFERENCES lineages (guild_id, board_id, lineage_id)
) ENGINE=InnoDB DEFAULT CHARSET=ascii COLLATE=ascii_bin;

CREATE TABLE audit_events (
    event_id BINARY(16) NOT NULL PRIMARY KEY,
    event_version SMALLINT UNSIGNED NOT NULL,
    occurred_at_utc DATETIME(6) NOT NULL,
    scope_kind ENUM('system','guild','board') NOT NULL,
    guild_id VARBINARY(20) NULL,
    board_id BINARY(16) NULL,
    actor_kind ENUM('user','system','operator') NOT NULL,
    actor_ref VARBINARY(64) NOT NULL,
    action_code VARBINARY(64) NOT NULL,
    outcome ENUM('accepted','denied','failed') NOT NULL,
    reason_code VARBINARY(64) NOT NULL,
    policy_generation BIGINT UNSIGNED NULL,
    correlation_id BINARY(16) NOT NULL,
    KEY ix_audit_scope (guild_id, board_id, occurred_at_utc, event_id),
    CONSTRAINT fk_audit_guild FOREIGN KEY (guild_id) REFERENCES guilds (guild_id),
    CONSTRAINT fk_audit_board FOREIGN KEY (guild_id, board_id) REFERENCES boards (guild_id, board_id),
    CONSTRAINT ck_audit_version CHECK (event_version = 1),
    CONSTRAINT ck_audit_scope CHECK (
        (scope_kind = 'system' AND guild_id IS NULL AND board_id IS NULL AND policy_generation IS NULL)
        OR (scope_kind = 'guild' AND guild_id IS NOT NULL AND board_id IS NULL)
        OR (scope_kind = 'board' AND guild_id IS NOT NULL AND board_id IS NOT NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=ascii COLLATE=ascii_bin;

CREATE TABLE deletion_jobs (
    guild_id VARBINARY(20) NOT NULL,
    job_id BINARY(16) NOT NULL,
    job_version SMALLINT UNSIGNED NOT NULL,
    target_kind ENUM('guild','board','subject') NOT NULL,
    board_id BINARY(16) NULL,
    subject_ref VARBINARY(64) NULL,
    phase ENUM('fenced','propagating','live_complete','complete') NOT NULL,
    failure_code VARBINARY(64) NULL,
    PRIMARY KEY (guild_id, job_id),
    KEY ix_deletion_board (guild_id, board_id, phase),
    KEY ix_deletion_subject (guild_id, subject_ref, phase),
    CONSTRAINT fk_deletion_guild FOREIGN KEY (guild_id) REFERENCES guilds (guild_id),
    CONSTRAINT fk_deletion_board FOREIGN KEY (guild_id, board_id) REFERENCES boards (guild_id, board_id),
    CONSTRAINT ck_deletion_version CHECK (job_version = 1),
    CONSTRAINT ck_deletion_failure CHECK (failure_code IS NULL OR phase = 'propagating'),
    CONSTRAINT ck_deletion_target CHECK (
        (target_kind = 'guild' AND board_id IS NULL AND subject_ref IS NULL)
        OR (target_kind = 'board' AND board_id IS NOT NULL AND subject_ref IS NULL)
        OR (target_kind = 'subject' AND board_id IS NULL AND subject_ref IS NOT NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=ascii COLLATE=ascii_bin;
