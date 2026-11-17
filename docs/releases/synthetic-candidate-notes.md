Version: 0.0.0-synthetic
Revision: 65e052dc2c923439890d50deac1d542799942666
Artifact SHA-256: 971cbeb2df5e1ff25b024eac8c86c5a56fc6666845e2fcda563c8f29aa71b4fe

# Synthetic candidate release notes

This documentation example uses a synthetic version and illustrative
payload. The revision names the source baseline used for the policy work.
Release approval, publication and deployment evidence are pending their
respective gates.

## Changes, compatibility and support

The sample payload contains a single text file, `example.txt`, with the
UTF-8 bytes `Guildboard synthetic release notes example` followed by one
LF. The header digest is the SHA-256 of the resulting checksum-index line
(file SHA-256, two ASCII spaces, `example.txt`, LF). A real candidate also
requires the complete indexed payload and provenance specified by the
[T13 contract](../specifications/GB-T13-S1-documentation-release-contract.md#release-evidence-schema).

This sample exercises no HTTP API, WebSocket, data/export, configuration or
operator interface. Supported ranges, deprecations and support dates for
actual releases require the maintainer's release record.

## Migration and recovery

The text payload changes no data, configuration or services, so the example
requires no migration. If local sample preparation is interrupted, regenerate
the text bytes and checksum-index line and check the header digest again.

## Known issues

The example covers note formatting and digest calculation. Candidate bundle
validation, hosted review and release verification require their own evidence.
See the [verification handoff](../release-versioning.md#verification-handoff).

## License notices

Guildboard's repository license is [MIT](../../LICENSE). The sample text
contains no third-party dependencies or assets. The payload and dependency
review for an actual release determines its third-party notices.

## Test and deployment evidence

The [T13 contract acceptance record](https://github.com/CompleteTech-DiscordApps/guildboard/issues/421#issuecomment-6963209428)
records 16 passing synthetic model tests and six passing default-branch
workflows on revision `60b3b53587c1a5a046d12c5c104c1150b89a1964`. That evidence
covers the accepted contract revision. Verification of this example is
tracked in [#442](https://github.com/CompleteTech-DiscordApps/guildboard/issues/442).
Real Discord checks and GoDaddy Linux VPS deployment and recovery evidence
remain pending the applicable release gates.
