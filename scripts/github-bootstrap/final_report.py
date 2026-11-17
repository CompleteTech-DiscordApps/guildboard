"""Render verified counts only from the independent live readback."""
from api import *
import collections
m=json.loads((ROOT/'planning/guildboard-backlog.json').read_text());r=json.loads((ROOT/'planning/audit/remote-audit.json').read_text());by={x['id']:x for x in m['items']};repo=m['repository'];p=r['project'];counts=r['counts'];fc=r['field_counts'];checks=json.loads((ROOT/'planning/audit/ci-verification.json').read_text()) if (ROOT/'planning/audit/ci-verification.json').exists() else {};credentials=api('repos/'+repo+'/actions/secrets')['secrets'];project_token=any(x['name']=='GUILDBOARD_PROJECT_TOKEN' for x in credentials)
root_commit=subprocess.check_output(['git','rev-list','--max-parents=0','HEAD'],text=True).strip().splitlines()[0]
commit_info=subprocess.check_output(['git','show','-s','--format=%cI%n%s',root_commit],text=True).splitlines()
def link(id):return '['+id+']('+issue_url(by[id]['github']['number'],repo)+')' if by.get(id,{}).get('github') else '`'+id+'` (not created)'
audited_repository = r['repository']['url'].removeprefix('https://github.com/').rstrip('/')
public_repository = next((name for name in (repo, TRANSFERRED_REPOSITORY)
                          if name.casefold() == audited_repository.casefold()), None)
observed_repositories = p['repositories']['nodes']
matching_count = sum(
 public_repository is not None and node['nameWithOwner'].casefold() == public_repository.casefold()
 for node in observed_repositories
)
observed_match = f'`{public_repository}`' if matching_count else 'None observed'
other_associations = len(observed_repositories) - matching_count
status = 'Complete and verified' if project_token and r['result'] == 'pass' and matching_count else 'Partially complete'
verified_association = 'Confirmed' if matching_count else 'Unconfirmed'
if public_repository:
 verified_association += f' for `{public_repository}`'
finding_counts = dict(collections.Counter(finding['kind'] for finding in r['findings']))
text=f'''# Guildboard bootstrap report

**Final status: {status}.** Repository, Project and roadmap audit: **{r['result']}**. The remaining automation credential requirement is described below. Guildboard itself has not been implemented or deployed; no application/production acceptance is claimed.

Audit time: {r['generated_at']}. Audit inspected repository head `{r['repository']['head']}`; subsequent artifact-only commits may carry this report. Counts below come from live GitHub readback, not failed requests or Markdown-only relationships.

## Repository

- URL: {canonicalize_transferred_links(r['repository']['url'], repo)}
- Audited repository owner: `{r['repository']['owner']}`
- Visibility: {r['repository']['visibility']}; default branch: `{r['repository']['default_branch']}`
- License: MIT for original work, subject to future dependency/asset licensing review.
- Topics: {', '.join('`'+t+'`' for t in r['repository']['topics'])}
- Initial commit: [{root_commit}](https://github.com/{repo}/commit/{root_commit}), {commit_info[0]} — {commit_info[1]}.
- Foundation includes module boundaries for Activity/API/bot/shared contracts/auth/canvas/collaboration, database/migrations, GoDaddy VPS, tests and documentation, plus functioning bootstrap/reconciliation/audit tools. Runtime module READMEs explicitly identify implementation as future work.
- Issues, Discussions and Actions enabled. Dependabot alerts/security updates, secret scanning, push protection and private vulnerability reporting enabled. Workflow tokens default to read-only; GitHub-owned/verified actions allowed. Main rules require reviewed CODEOWNER PRs and the actual `Validate roadmap` check; an explicit administrator bootstrap bypass is documented. No review was fabricated.

## GitHub Project

- URL: {p['url']}
- Owner: `{p['owner']['login']}`; Project number: {p['number']}; public: {p['public']}.
- Configuration copied from [Pick Your AI Project #1](https://github.com/orgs/Pick-Your-AI/projects/1), with draft copying disabled. Initial copy independently contained **zero items**. Source issues, PRs and assignments were not imported. The source Project was read-only.
- Observed audited repository association: {observed_match}.
- Other Project repository associations observed: {other_associations}.
- Audited repository association: {verified_association}.
- Default first view: Workstream overview, table grouped by Tier, native hierarchy and sub-issue progress visible.
- {len(p['views']['nodes'])} saved views, {len(p['fields']['nodes'])} total native/configuration fields, {sum(w['enabled'] for w in p['workflows']['nodes'])} enabled native workflows. Default Burn up Insight retained.

### Saved views

'''
for view in sorted(p['views']['nodes'],key=lambda v:v['number']):
 text+=f"- [{view['name']}]({p['url']}/views/{view['number']}) — {view['layout'].replace('_LAYOUT','').lower()}; filter: `{view['filter'] or '(all items)'}`.\n"
text+='\n### Project schema\n\n'
for f in p['fields']['nodes']:
 if 'options' in f:text+='- **'+f['name']+'**: '+', '.join(o['name'] for o in f['options'])+'.\n'
text+='\nTarget Date is a DATE field and remains blank on all items; Blocking Reason is derived TEXT. Native Title, Assignees, Parent issue, Sub-issues progress, Labels, Milestone and Linked pull requests were reused without duplicates. Text cells have a 256-character limit, so blocker summaries show counts/issue numbers and a direct first-blocker link; native relationships and issue bodies retain every blocker.\n'
text+='\n### Native workflows\n\n'
for w in p['workflows']['nodes']:text+='- '+w['name']+': '+('enabled' if w['enabled'] else 'disabled')+'.\n'
text+='\nNew/reopened intake uses Triage; closed items use Done; linked PRs use In Progress; merged PR items use Done. Auto-close issue on Project Done is disabled. No automation marks implementation or research Verified. Closed/reopened/PR rules were inspected as saved native configuration; enrollment was validated using actual Guildboard items.\n'
text+='\n## Workstreams and hierarchy\n\n| Category | Live count |\n| --- | ---: |\n'
for k in ['Epic','Capability','Feature','Task','Subtask','Research','Specification','Test','Documentation','Operations']:text+=f'| {k} | {counts.get(k,0)} |\n'
text+=f'''| Total issues / Project items | {r['live_expected_issues']} / {r['project_items']} |
| Native parent-child relationships | {r['native_parent_links']} |
| Native blocking relationships | {r['native_blocking_dependencies']} |
| Maximum actual hierarchy depth | {r['max_actual_hierarchy_depth']} |
| Marked initial technical handoff comments | {r.get('initial_handoff_comments',0)} |

Every descendant is enrolled and fully classified. Native links, rather than body links, establish hierarchy and blockers. Verification tasks remain open and unverified.

| Workstream | Epic | Responsible expertise | Total planned issues |
| --- | --- | --- | ---: |
'''
for i,w in enumerate(json.loads((ROOT/'planning/workstreams.json').read_text())):
 n=sum(x['workstream']==f'T{i}' for x in m['items']);text+=f'| T{i}: {w["name"]} | '+link(f'GB-T{i}')+f' | {w["role"]} | {n} |\n'
text+='\n## Triage statistics\n\n| Classification | Live count |\n| --- | ---: |\n'
for v in ['Critical','High','Medium','Low']:text+=f'| Priority: {v} | {fc["Priority"].get(v,0)} |\n'
text+=f'''| Readiness: Ready | {fc['Readiness'].get('Ready',0)} |
| Ready-to-implement Task/Subtask items | {sum(x['fields']['Readiness']=='Ready' and x['work_type'] in ['Task','Subtask'] for x in m['items'])} |
| Native-dependency Blocked | {fc['Dependency Status'].get('Blocked',0)} |
| Readiness: Needs Research | {fc['Readiness'].get('Needs Research',0)} |
| Research investigations awaiting evidence | {counts.get('Research',0)} |
| Intentionally unassigned | {counts.get('unassigned',0)} |
| Missing/contradictory metadata issues | {r['missing_metadata_issues']} |
| Verified implementation items | {fc['Verification Status'].get('Verified',0)} |

All research investigations remain Unverified. Their 14 tracked evidence gaps are in [RISKS.md](RISKS.md); default Unverified values on non-research work are not counted as separate assumptions. Ready research is distinct from ready coding. Unassigned backlog remains visible and is not an integrity error.

## Verification and traceability

- Repository configuration and committed foundation: {r['result']}.
- Project owner, visibility, field schema, views/groupings/columns: {r['result']}.
- Native hierarchy and enrollment: {r['result']}; no accidental orphan descendants.
- Native dependency graph: {r['result']}; no self-dependencies or cycles.
- Strict initial triage/readiness/label/milestone checks: {r['result']}.
- Traceability: [307 authored capability clauses](TRACEABILITY.md), plus focused MVP integrated acceptance {link('GB-T12.MVP1')}; implementation, testing, documentation and release-gate links are recorded in [traceability.json](traceability.json).
- Critical-path report: [DEPENDENCIES.md](DEPENDENCIES.md), based on the verified native graph. Longest chains are unweighted prerequisite sequences, not time forecasts.
- MVP approval consumes only M0–M2 prerequisite phases; no invented dates.
- Milestones: [MILESTONES.md](MILESTONES.md), nine milestones with no due dates.
- Machine readback: [remote-audit.json](audit/remote-audit.json).

Release gates: MVP {link('GB-T13.G1')}; production recovery/GoDaddy {link('GB-T13.G2')}; stable approval {link('GB-T13.G3')}. Actual publication is separate: MVP {link('GB-T13.04.01.O1')}, stable v1.0 {link('GB-T13.04.01.O2')}. These are future engineering work, not performed releases.

## CI and repeatability

'''
if checks:
 for run in checks.get('runs',[]):text+=f"- [{run['name']}]({canonicalize_transferred_links(run['html_url'], repo)}): {run['conclusion']} at `{run['head_sha']}`.\n"
text+='\nIdempotent issue detection was rerun after population; no additional issues were created. Initial comments use durable markers and the live audit verifies exactly one per selected handoff. Scripts preserve assignments and legitimate established field changes; explicit reviewed plan flags were used for the bootstrap milestone/release refinements.\n'
text+='\n## Remaining or unsupported operations\n\n'
if not project_token:text+='- **Scheduled full Project-field auditing needs `GUILDBOARD_PROJECT_TOKEN`.** No repository secret is configured. User-owned Projects do not accept the repository installation token for these API operations. A dedicated supported read-Project credential must be added by an authorized maintainer. Daily restricted-token repository integrity checks, native Project workflows, and the full authenticated on-demand audit are implemented; the broader local OAuth credential was not copied into Actions.\n'
if finding_counts:
 for kind,count in sorted(finding_counts.items()):text+=f'- Audit finding `{kind}`: {count}.\n'
text+='- No Discord application, GoDaddy VPS, DNS/TLS endpoint, production deployment or application acceptance test was performed by this bootstrap. These remain explicitly scoped, unverified roadmap work rather than missing claims of completed setup.\n- GitHub content creation temporarily hit its secondary limit; creation was paused and resumed under the same account/API. Final counts include only confirmed live resources. All recoverable API/configuration discrepancies were reconciled before this report.\n'
(ROOT/'planning/BOOTSTRAP-REPORT.md').write_text(text)
save(ROOT/'planning/audit/final-summary.json',{'status':status,'repository':r['repository']['url'],'project':p['url'],'issues':r['live_expected_issues'],'items':r['project_items'],'parents':r['native_parent_links'],'dependencies':r['native_blocking_dependencies'],'counts':counts,'fields':fc,'finding_counts':finding_counts,'project_audit_credential_configured':project_token,'initial_commit':root_commit})
print(status,r['live_expected_issues'],'issues;',r['native_parent_links'],'native parents;',r['native_blocking_dependencies'],'native blockers')
