"""Run final captures serially so emulator instances never compete for time."""
import subprocess,sys
from pathlib import Path
here=Path(__file__).resolve().parent
for version in ('photos','candidate','roster','ordinary'):
    subprocess.run([sys.executable,str(here/'run.py'),'capture',version],check=True)
