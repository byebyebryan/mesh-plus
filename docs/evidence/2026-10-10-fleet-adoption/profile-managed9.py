import sys,runpy
from pathlib import Path
home=Path.home()
sys.dont_write_bytecode=True
roots=['.local/share/mesh-plus/0.1.0a9/python',*[f'.local/share/mesh-plus/dependencies/{n}' for n in ['attrs','jsonschema','jsonschema-specifications','referencing','rpds-py']],'.local/share/tmux-observer/python','.local/share/agent-observer/0.5.0a12-e292e689a1dd1b32-mesh-a9/lib/python3.14/site-packages']
sys.path[:0]=[str(home/r) for r in roots]
script=sys.argv.pop(1)
runpy.run_path(script,run_name='__main__')
