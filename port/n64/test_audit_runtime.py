"""Presentation evidence must not equate rounded FPS with a missed retrace."""
import json
from pathlib import Path
import tempfile
import unittest

from audit_models import runtime_benchmarks_html


class RuntimeReportTests(unittest.TestCase):
    def render(self, data, screenshot=None):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / 'runtime-fixture-results.json').write_text(json.dumps(data))
            if screenshot:
                (output / screenshot).write_bytes(b'fixture')
            return runtime_benchmarks_html(output)

    def test_legacy_report_needs_no_vi_fields(self):
        document = self.render({'all': {'frames': 3000, 'fps': 40.0},
                                'gpu_completed': {'all': {'frames': 3000, 'fps': 40.0}}})
        self.assertIn('CPU frame acquisition intervals', document)
        self.assertIn('RDP completion callback cadence', document)
        self.assertNotIn('<h3>Fresh simulation poses presented at VI</h3>', document)

    def test_two_retraces_accepts_truncated_29_9_fps(self):
        screenshot = 'VI & <frame>.png'
        document = self.render({'vi_evidence': screenshot, 'vi_presented': {'all': {
            'poses': 2248, 'fps': 29.9, 'p95_ms': 33.4, 'max_ms': 33.5,
            'max_gap_vi': 2, 'gap_1_vi': 0, 'gap_2_vi': 2248, 'gap_over_2_vi': 0,
            'buffer_flips': 2248, 'same_pose_flips': 0}}}, screenshot)
        vi = document.split('<h3>Fresh simulation poses presented at VI</h3>')[1]
        self.assertIn('<td>2,248</td>', vi)  # the poses alias is recorded, not inferred
        self.assertIn('<td class="">29.9</td>', vi)
        self.assertNotIn('class="down"', vi)
        self.assertIn('VI%20%26%20%3Cframe%3E.png', vi)
        self.assertIn('runtime-fixture-results.json', vi)
        self.assertNotIn('Missed presentation deadlines</th>', vi)
        self.assertNotIn('Input sample to VI: mean ms</th>', vi)

    def test_misses_duplicates_and_lost_ticks_are_explicit(self):
        document = self.render({'vi_presented': {'all': {
            'frames': 2100, 'fps': 28.0, 'max_gap_vi': 4, 'gap_over_2_vi': 3,
            'same_pose_flips': 5, 'missed_deadlines': 6, 'skipped_poses': 7,
            'dropped_ticks': 2, 'sample_to_vi_mean_ms': 51,
            'ready_to_vi_max_ms': 40}}})
        vi = document.split('<h3>Fresh simulation poses presented at VI</h3>')[1]
        self.assertIn('<td class="">28.0</td>', vi)  # flag the measured gaps, not FPS
        for label, value in [('Flips repeating the same pose', 5),
                             ('Missed presentation deadlines', 6),
                             ('Skipped simulation poses', 7), ('Catch-up ticks dropped', 2)]:
            self.assertIn(f'<th>{label}</th><td class="down">{value}</td>', vi)
        self.assertIn('<td class="down">4</td>', vi)
        self.assertIn('<td class="down">3</td>', vi)
        self.assertIn('Input sample to VI: mean ms</th><td class="">51.0', vi)
        self.assertNotIn('Input sample to VI: max ms</th>', vi)

    def test_partial_phases_and_unknown_telemetry(self):
        document = self.render({'vi_presented': {
            'all': {'frames': 123, 'missed_deadlines': None, 'buffer_flips': True},
            'vehicles': {'poses': 45, 'fps': 29.9}, 'combat': None}})
        vi = document.split('<h3>Fresh simulation poses presented at VI</h3>')[1]
        self.assertIn('rowspan="2"', vi)
        self.assertIn('<th>Vehicles</th><td>45</td>', vi)
        self.assertNotIn('<th>Combat</th>', vi)
        self.assertNotIn('VI presentation telemetry', vi)
        self.assertIn('—', vi)

    def test_vi_only_does_not_invent_acquisition_or_completion(self):
        document = self.render({'measurement_mode': 'vi_only', 'vi_presented': {'all': {
            'poses': 2229, 'fps': 29.7, 'missed_deadlines': 15}}})
        self.assertIn('VI-only runs intentionally omit', document)
        self.assertIn('<h3>Fresh simulation poses presented at VI</h3>', document)
        self.assertNotIn('<h3>CPU frame acquisition intervals</h3>', document)
        self.assertNotIn('<h3>RDP completion callback cadence</h3>', document)
        self.assertNotIn('Their acquisition FPS', document)
        self.assertNotIn('Submitted vertices', document)
        self.assertIn('Missed presentation deadlines</th><td class="down">15', document)

    def test_optional_queue_and_heap_are_not_deadline_failures(self):
        document = self.render({'vi_presented': {'all': {
            'poses': 2238, 'display_buffers': 4, 'held_queue_peak': 3,
            'sdk_ready_peak': 1, 'submitted_not_presented_peak': 3,
            'heap_free_kib': 923}}})
        self.assertIn('Display surfaces</th><td class="">4', document)
        self.assertIn('Held completed surfaces: whole-run peak</th><td class="">3', document)
        self.assertIn('Live free heap before teardown: KiB</th><td class="">923', document)
        self.assertNotIn('class="down"', document)
        self.assertNotIn('Missed presentation deadlines</th>', document)


if __name__ == '__main__':
    unittest.main()
