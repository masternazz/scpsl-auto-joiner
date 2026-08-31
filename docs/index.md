# Project documentation

This index separates current maintenance guidance from historical research and
release records. Start here when taking over the project.

## Maintainer path

1. [Handoff guide](handoff.md) — current source of truth, invariants, module map,
   and first-session checklist.
2. [Development guide](development.md) — environment setup, test commands, and
   local startup.
3. [Architecture](architecture.md) — runtime layers, data flow, services, and
   persistence boundaries.
4. [Release process](release-process.md) — versioning, packaging, verification,
   and publishing.
5. [Private-server acceptance](private-server-acceptance.md) — authorized live
   validation without using public servers.

## Product and operations

- [Product design](product-design.md)
- [Feature and release matrix](roadmap-status.md)
- [Known WebView startup issue](known-issue-webview-startup.md)
- [README visual maintenance](readme-visuals.md)
- [Owned-server companion](owned-server-companion.md)
- [Security review](security-review.md)

## Historical material

Files under [`research/`](research/) and dated release notes document why older
choices were made. They are useful evidence, but they do not override current
code, tests, the handoff guide, or the latest release notes.

The repository intentionally does not contain private server addresses, SSH
configuration, Pelican credentials, Discord credentials, tokens, user AppData,
or captured game logs. Authorized infrastructure access must be supplied through
the owner's private operations documentation.
