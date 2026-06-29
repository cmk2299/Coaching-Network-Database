"""Contract test: the public-API docstring in lib/network_stages.py must
match the actual module exports. Prevents doc drift as new stages land.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "execution"))
from lib import network_stages  # noqa: E402


def test_every_documented_symbol_is_a_real_export():
    """Every name mentioned in the docstring's bullet list (• xxx(…)) or
    constants section must exist as a real attribute of the module."""
    doc = network_stages.__doc__ or ""
    bullet_names = set(re.findall(r"•\s+([A-Za-z_][A-Za-z0-9_]*)", doc))
    assert bullet_names, "docstring has no bulleted symbols — did the format change?"
    # CAT_ORDER, CURRENT_SEASON, MAX_STAFF_SEASON_GAP also appear in bullets
    missing = sorted(n for n in bullet_names if not hasattr(network_stages, n))
    assert not missing, f"Docstring mentions symbols not in module: {missing}"


def test_no_undocumented_callable_public_stage():
    """Every public callable in network_stages (no leading _) should appear in
    the docstring — otherwise readers miss it."""
    doc = network_stages.__doc__ or ""
    documented = set(re.findall(r"•\s+([A-Za-z_][A-Za-z0-9_]*)", doc))
    actual_callables = {
        name for name in dir(network_stages)
        if not name.startswith("_")
        and callable(getattr(network_stages, name))
        and getattr(network_stages, name).__module__ == "lib.network_stages"
    }
    undocumented = sorted(actual_callables - documented)
    assert not undocumented, (
        f"Public callables not in docstring (add to network_stages.py header): "
        f"{undocumented}"
    )
