import unittest

import pandas as pd

from Web.Backend.sldc_source import parse_sldc_snapshot


SNAPSHOT_HTML = """
<html>
  <div>DISCOM DRAWL (03:18:38 Hrs)</div>
  <table>
    <tr><th>Discom</th><th>Schedule</th><th>Drawl</th><th>OD/UD</th></tr>
    <tr><td>BRPL</td><td>877</td><td>983</td><td>106</td></tr>
    <tr><td>BYPL</td><td>407</td><td>471</td><td>64</td></tr>
    <tr><td>TPDDL</td><td>666</td><td>496</td><td>-170</td></tr>
    <tr><td>NDMC</td><td>117</td><td>80</td><td>-37</td></tr>
    <tr><td>MES</td><td>16</td><td>14</td><td>-2</td></tr>
    <tr><td>RAILWAY</td><td>15</td><td>19</td><td>4</td></tr>
    <tr><td>Total</td><td>2098</td><td>2064</td><td>-34</td></tr>
    <tr><td>Total (DTL End)</td><td>2115</td><td>2081</td><td>-34</td></tr>
  </table>
</html>
"""


class SldcSourceTests(unittest.TestCase):
    def test_parses_all_entities_from_drawl_column_and_aligns_snapshot_time(self) -> None:
        reading = parse_sldc_snapshot(
            SNAPSHOT_HTML,
            now=pd.Timestamp("2026-11-20 03:22:00", tz="Asia/Kolkata"),
        )

        self.assertEqual(reading["timestamp"], pd.Timestamp("2026-11-20 03:15:00", tz="Asia/Kolkata"))
        self.assertEqual(reading["brpl_mw"], 983.0)
        self.assertEqual(reading["tpddl_mw"], 496.0)
        self.assertEqual(reading["railways_mw"], 19.0)
        self.assertEqual(reading["delhi_total_mw"], 2_064.0)

    def test_assigns_pre_midnight_snapshot_to_previous_local_day(self) -> None:
        html = SNAPSHOT_HTML.replace("03:18:38", "23:58:38")
        reading = parse_sldc_snapshot(
            html,
            now=pd.Timestamp("2026-11-20 00:01:00", tz="Asia/Kolkata"),
        )

        self.assertEqual(reading["timestamp"], pd.Timestamp("2026-11-19 23:45:00", tz="Asia/Kolkata"))

    def test_rejects_a_page_missing_a_tracked_entity(self) -> None:
        html = SNAPSHOT_HTML.replace("<tr><td>RAILWAY</td><td>15</td><td>19</td><td>4</td></tr>", "")
        with self.assertRaisesRegex(ValueError, "railways_mw"):
            parse_sldc_snapshot(
                html,
                now=pd.Timestamp("2026-11-20 03:22:00", tz="Asia/Kolkata"),
            )


if __name__ == "__main__":
    unittest.main()
