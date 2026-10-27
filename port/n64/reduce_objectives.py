"""Reuse the accepted skinning/reduction pipeline for objective viewmodels.

Run in an independent Blender background process, after extract_objectives.py.
"""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from reduce_firstperson import reduce_firstperson

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source');p.add_argument('output')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    reduce_firstperson(a.source,a.output,hand_budget=200,hand_topology='connected',
                       gun_budgets={'flag':240,'ball':240})
