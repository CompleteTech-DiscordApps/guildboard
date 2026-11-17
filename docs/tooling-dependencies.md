# Configuration test tooling

Introduced by GB-T0.03.02.T1.S1 (#451), 2026-10-24 UTC. The config package has no runtime dependencies. Compiler and Node declarations are development-only, installed from the npm registry through the root lockfile with scripts disabled.

| Dependency | Pin | Declared license | Purpose |
| --- | --- | --- | --- |
| TypeScript | 5.9.3 | Apache-2.0 | Compile/type-check the narrow ES2022 package and tests; chosen as a known non-native compiler with no dependency tree |
| @types/node | 24.19.2 | MIT | Node 24 built-in test/assert, filesystem and child-process declarations |
| undici-types | 7.24.6 (resolved transitive pin) | MIT | HTTP-client declarations required by @types/node |

The Node declarations bring `undici-types` transitively; its resolved version, integrity and license are recorded by `package-lock.json`. No compiler or dependency upgrade policy for the whole application is decided here. Retain installed license notices if distributing tooling. This focused review does not clear future application dependencies, fonts, icons, user assets or release packaging; those remain the T0 licensing workstream's responsibility.

Installed license files for all three external packages were inspected and hashed in [the evidence record](evidence/config-tooling-2026-10-24.json). `npm audit --json` reported zero advisories on 2026-10-24 UTC. A zero-advisory result is a point-in-time registry observation, not a security certification.
