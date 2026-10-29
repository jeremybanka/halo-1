"""Run the matched timing matrices serially; no competing emulator instances."""
import subprocess,sys
from pathlib import Path
run=Path(__file__).with_name('run.py')
for version in ('before','after'):
    subprocess.run([sys.executable,str(run),'capture',version,'perf'],check=True)
subprocess.run([sys.executable,str(run),'capture','after','roster-photos'],check=True)
subprocess.run([sys.executable,str(run),'capture','before','roster-photos'],check=True)
