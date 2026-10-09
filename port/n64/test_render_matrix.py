"""Check the renderer's sibling-stack contract against the installed Tiny3D API.

Symbolic matrix products preserve operand identity and order without assuming
floating-point associativity. This proves the same inputs reach the unchanged
RSP multiplication for every draw, including empty views and consecutive views.
It does not replace target pixel comparison of the complete renderer.
"""
import argparse
from pathlib import Path
import random
import re


def function(source, name):
    match = re.search(r'\b' + re.escape(name) + r'\([^;{}]*\)\s*\{', source)
    assert match, name
    start = match.end()
    depth = 1
    for end in range(start, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if depth == 0:
            return source[start:end]
    raise AssertionError('Unterminated function: ' + name)


def compact(source):
    return re.sub(r'\s+', '', re.sub(r'/\*.*?\*/|//[^\n]*', '', source, flags=re.S))


def check_source(main, sdk):
    source = main.read_text()
    view = compact(function(source, 'draw_view'))
    assert view.count('t3d_viewport_attach(vp);') == 1
    assert view.count('t3d_matrix_push_pos(1);') == 1
    assert view.count('t3d_matrix_pop(1);') == 1
    assert view.index('rspq_block_run(world_blocks[b]);') < view.index('t3d_matrix_push_pos(1);')
    assert view.index('t3d_matrix_push_pos(1);') < view.index('t3d_matrix_set(')
    assert view.rstrip().endswith('t3d_matrix_pop(1);')
    assert 'return' not in view, 'An early return could leak stack depth'
    assert 't3d_matrix_push(' not in source
    for name in ('instance', 'small_model_instance'):
        helper = compact(function(source, name))
        assert helper.count('t3d_matrix_set(matrix,true);') == 1
        assert 't3d_matrix_pop' not in helper and 't3d_matrix_push' not in helper
    calls = re.findall(r't3d_matrix_set\(([^;]+)\);', source)
    assert len(calls) == 10  # Includes the independent Covenant wreck mesh.
    assert all(c.endswith(',true') for c in calls), 'Each draw must multiply the camera below it'
    # All non-helper sets remain within the single sibling scope.
    assert view.count('t3d_matrix_set(') == len(calls) - 2

    api = (sdk / 'src/t3d/t3d.c').read_text()
    assert 't3d_matrix_stack((void*)mat,0,doMultiply,false);' in compact(function(api, 't3d_matrix_set'))
    assert 't3d_matrix_stack(NULL,stackAdvance,false,true);' in compact(function(api, 't3d_matrix_push_pos'))
    assert 't3d_matrix_stack(NULL,stackAdvance,false,false);' in compact(function(api, 't3d_matrix_pop'))
    rspl = compact((sdk / 'src/t3d/rsp/inc/matrixStack.rspl').read_text())
    for contract in ('stackPtr+=stackAdvance;', 'if(onlyStackMove)exit;',
                     'if(stackAdvance<0)addressMat=stackPtr;',
                     'addrRDRAM=stackPtr-MATRIX_SIZE;',
                     'mulLeft=MATRIX_TEMP_MUL;', 'mulMat4Mat4(mulDest,mulLeft,dmaDest);'):
        assert contract in rspl, 'Unsupported Tiny3D matrix semantics: ' + contract


class Stack:
    def __init__(self):
        self.depth = 0
        self.memory = {}
        self.multiplies = 0

    def command(self, matrix=None, advance=0, multiply=False, only_move=False):
        self.depth += advance
        assert 0 <= self.depth <= 1
        if only_move:
            return
        if advance < 0:
            matrix = self.memory[self.depth]
        if multiply:
            matrix = ('mul', self.memory[self.depth - 1], matrix)
        self.memory[self.depth] = matrix
        self.current = matrix
        self.projected = ('mul', self.projection, matrix)
        self.multiplies += 1 + multiply

    def view(self, camera, projection):
        assert self.depth == 0, 'Projection/view replacement requires the camera slot'
        self.projection = projection
        self.command(camera)


def check_sequences():
    rng = random.Random(0xCE064)
    old, new = Stack(), Stack()
    draws = views = 0
    for frame in range(512):
        for player in range((1, 2, 4)[frame % 3]):
            camera = ('camera', frame, player)
            projection = ('projection', frame, player, rng.choice(('normal', 'pistol2x', 'sniper10x')))
            old.view(camera, projection)
            new.view(camera, projection)
            # Terrain must see exactly the freshly attached camera, without
            # an object left on the stack from a prior viewport.
            assert old.projected == new.projected == ('mul', projection, camera)
            new.command(advance=1, only_move=True)
            groups = ['vehicle body', 'wheel world pose', 'turret world pose',
                      'barrel world pose', 'spartan', 'held world pose',
                      'pickup', 'projectile', 'explosion', 'first person']
            # Explicit empty views plus varied counts exercise every branch
            # pattern, zero visible bodies, all rig parts, and FP exclusion.
            for i in range(0 if frame % 17 == 0 else rng.randrange(1, 80)):
                matrix = ('world', frame, player, i, rng.choice(groups))
                old.command(matrix, advance=1, multiply=True)
                new.command(matrix, multiply=True)
                expected = ('mul', projection, ('mul', camera, matrix))
                assert old.projected == new.projected == expected
                assert old.current == new.current
                old.command(advance=-1)
                draws += 1
            new.command(advance=-1)
            assert old.depth == new.depth == 0
            assert old.current == new.current == camera
            views += 1
    assert new.multiplies < old.multiplies
    # A set without multiplication must fail the same expected draw contract.
    wrong = Stack(); wrong.view('camera', 'projection')
    wrong.command(advance=1, only_move=True); wrong.command('world')
    assert wrong.projected != ('mul', 'projection', ('mul', 'camera', 'world'))
    return views, draws, old.multiplies - new.multiplies


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tiny3d', type=Path, default=root.parent / 'n64-3d-splitscreen/.build/tiny3d')
    args = parser.parse_args()
    check_source(root / 'port/n64/main.c', args.tiny3d)
    views, draws, removed = check_sequences()
    print(f'Sibling matrices: {views} views, {draws} draws preserve exact multiplication operands/order; '
          f'{removed} redundant matrix recalculations removed in test sequences')
