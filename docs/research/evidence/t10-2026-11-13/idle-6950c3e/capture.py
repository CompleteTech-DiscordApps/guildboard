import argparse,importlib.util,json,subprocess,sys,time,hashlib
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--repository', type=Path, required=True)
parser.add_argument('--nginx-binary', required=True)
parser.add_argument('--output', type=Path, required=True)
args=parser.parse_args()
root=args.repository.resolve()
source_paths=('scripts/research/t10-nginx-probe.py','scripts/research/t10-proxy-fixture.py','scripts/research/t10-capture-sources.py','tests/research/t10-test-nginx-probe.py','docs/research/t10-nginx-probe.conf')
tested='6950c3e253ead359d621102ebf068e03b5f3fef7'
for path in source_paths:
    expected=subprocess.check_output(['git','-C',str(root),'show',tested+':'+path])
    if (root/path).read_bytes()!=expected:
        raise RuntimeError('Source differs from tested revision: '+path)
spec=importlib.util.spec_from_file_location('idle_tests',root/'tests/research/t10-test-nginx-probe.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
old_sha='623dd1f0240f48779f590f34db36f62e4a42bf20'
old_bytes=subprocess.check_output(['git','-C',str(root),'show',old_sha+':scripts/research/t10-proxy-fixture.py'])
old_module=type(m.FIXTURE)('old_fixture');exec(compile(old_bytes,'<git:'+old_sha+':t10-proxy-fixture.py>','exec'),old_module.__dict__)
fixed=m.FIXTURE;case=m.FixtureIdleRegression()
m.FIXTURE=old_module
before=case.exchange_with_delays(handshake_delay=2)
m.FIXTURE=fixed
if not 1.5<=before<4.5:raise RuntimeError('old bug not reproduced')
try:case.exchange_with_delays(handshake_delay=2)
except fixed.ProbeFailure as error:after={'check':error.check,'detail':error.detail}
else:raise RuntimeError('new version accepted delayed handshake EOF')
valid=case.exchange_with_delays(handshake_delay=.1,idle_delay=2)
network=[m.PROBE.run_local(args.nginx_binary,control) for control in (None,*m.PROBE.HANDSHAKE_REJECTIONS,'publish-private-assets','long-read-timeout')]
if len(network[0].get('result',{}).get('checks',[]))!=12 or not all(x['passed'] for x in network[0]['result']['checks']):raise RuntimeError('Baseline failed')
if len(network)!=7 or not all(x.get('negative_control',{}).get('detected') for x in network[1:]):raise RuntimeError('Negative control failed')
if not 1.5<=valid<fixed.IDLE_CLOSE_DEADLINE:raise RuntimeError('Valid post-upgrade idle failed')
report={'tested_revision':tested,'checkout_revision':subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip(),'old_revision':old_sha,'old_fixture_sha256':hashlib.sha256(old_bytes).hexdigest(),'old_delayed_handshake_immediate_eof_accepted_elapsed':before,'new_delayed_handshake_immediate_eof_rejected':after,'new_postvalidated_upgrade_idle_elapsed':valid,'network':network}
args.output.write_text(json.dumps(report,indent=2)+'\n')
print('old false acceptance reproduced; fixed rejects; valid post-upgrade idle passes; actual Nginx baseline and six controls captured')
