import argparse, hashlib, importlib.machinery, importlib.util, json, sys
from pathlib import Path
from tempfile import TemporaryDirectory
p=argparse.ArgumentParser();p.add_argument('--gate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
loader=importlib.machinery.SourceFileLoader('installed_gate',str(a.gate));spec=importlib.util.spec_from_loader(loader.name,loader);g=importlib.util.module_from_spec(spec);sys.modules[spec.name]=g;loader.exec_module(g)
history=g._history_path();before=g._history_snapshot(history)
try:
 commands={n:g._resolve(n) for n in ('rofi-ssh-plus','rofi-tmux-plus')};env=g._clean_environment()
 hosts,local,revision=g._check_mesh(commands['rofi-ssh-plus'],env)
 g._check_inventory(commands['rofi-tmux-plus'],local,revision,env)
 g._check_ssh_recent_only(commands['rofi-ssh-plus'],env)
 g.LifecycleGate(commands['rofi-tmux-plus'],env).run(hosts,revision)
finally:
 if before is not None:g._assert_history_unchanged(before,history)
a.output.write_text(json.dumps(dict(state='passed',scope='installed SSH Host Mesh and Tmux inventory/disposable exact-reference lifecycle only',gateSha256=hashlib.sha256(a.gate.read_bytes()).hexdigest(),commands=commands,hosts=hosts,localHost=local,revision=revision,sshHistoryUnchanged=True,agentPlusMigration=False,physicalDesktopAcceptance=False),indent=2)+'\n')
