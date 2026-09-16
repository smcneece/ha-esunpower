"""Tests for select.py battery reserve percentage handling."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.sunpower.select import (
    RESERVE_PERCENTAGE_OPTIONS,
    SunPowerReservePercentageSelect,
)


def make_select(min_customer_soc="__unset__", data="__default__"):
    """Build a reserve select whose coordinator reports the given min_customer_soc.

    Pass data= to override the whole coordinator payload (for the missing-key
    and no-data cases); otherwise a battery_config block is built for you.
    """
    coordinator = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
    if data != "__default__":
        coordinator.data = data
    elif min_customer_soc == "__unset__":
        coordinator.data = {"battery_config": {}}
    else:
        coordinator.data = {"battery_config": {"min_customer_soc": min_customer_soc}}

    return SunPowerReservePercentageSelect(
        coordinator, MagicMock(), "ZT000000000000F0000", AsyncMock()
    )


def test_off_grid_reserve_is_reported_instead_of_unknown():
    """A reserve that isn't a 5% step must still be readable.

    Regression test for GitHub issue #96: a PVS reporting min_customer_soc=0.39
    rendered the select as "unknown". Home Assistant blanks a select whenever
    current_option is absent from options, and the hardcoded 5% list has no
    "39%" entry, so a perfectly valid reading looked like no reading at all.
    The PVS accepts any percentage and the SunStrong app sets it with a
    continuous slider, so off-grid values are easy to land on by accident.
    """
    select = make_select(0.39)
    assert select.current_option == "39%"
    assert "39%" in select.options


def test_current_option_is_always_in_options():
    """Home Assistant's SelectEntity contract: current_option must be in options.

    This is the invariant that actually produces the "unknown" symptom when
    broken, so assert it directly across on-grid and off-grid values rather
    than only checking the values themselves.
    """
    for min_soc in (0.05, 0.20, 0.39, 0.40, 0.57, 0.99, 1.00):
        select = make_select(min_soc)
        assert select.current_option in select.options, (
            f"min_customer_soc={min_soc} produced {select.current_option!r} "
            f"which is not in options - HA will render this as unknown"
        )


def test_on_grid_reserve_leaves_options_untouched():
    """A 5%-step reserve must not alter the menu.

    The fix folds the device's value into options only when it falls off the
    grid. For the common case the user should see the same tidy 20-entry list.
    """
    select = make_select(0.40)
    assert select.current_option == "40%"
    assert select.options == RESERVE_PERCENTAGE_OPTIONS


def test_off_grid_reserve_adds_exactly_one_option_in_numeric_order():
    """The folded-in value belongs in numeric position, not appended or sorted as text.

    Sorting these strings lexically puts "100%" before "15%", which would
    scramble the dropdown for every user, not just the one with an odd reserve.
    """
    select = make_select(0.39)
    assert len(select.options) == len(RESERVE_PERCENTAGE_OPTIONS) + 1
    assert select.options[select.options.index("39%") - 1] == "35%"
    assert select.options[select.options.index("39%") + 1] == "40%"
    assert select.options[-1] == "100%"


@pytest.mark.parametrize("min_soc,expected", [(0.29, "29%"), (0.57, "57%"), (0.58, "58%")])
def test_float_truncation_does_not_lose_a_percent(min_soc, expected):
    """round(), not int(), when scaling the 0-1 decimal to a percentage.

    float(0.29) * 100 == 28.999999999999996, so int() yielded "28%". Exactly
    three values in 1..100 are affected (0.29, 0.57, 0.58) and none land on the
    5% grid, so on its own this is invisible - it only shows up once off-grid
    values are displayable at all.
    """
    assert make_select(min_soc).current_option == expected


def test_reserve_is_none_when_the_pvs_has_not_reported_it():
    """No reading must stay None rather than becoming a fabricated percentage.

    Same failure mode as the ESS state-of-health bug in #95: defaulting a
    missing value to 0 makes "no data" indistinguishable from a real 0%.
    See #96 for this entity.
    """
    for data in (None, {}, {"other_key": {}}, {"battery_config": {}},
                 {"battery_config": {"min_customer_soc": None}}):
        select = make_select(data=data)
        assert select.current_option is None
        assert select.options == RESERVE_PERCENTAGE_OPTIONS


async def test_off_grid_reserve_can_be_reselected():
    """Selecting the folded-in value must write it, not log an error.

    async_select_option validates against the live options rather than the
    constant, so the value the device already holds stays selectable.
    """
    select = make_select(0.39)

    await select.async_select_option("39%")

    select._client.set_var.assert_called_once_with(
        "/ess/config/dcm/control_param/min_customer_soc", "0.39"
    )


async def test_invalid_option_is_still_rejected():
    """Widening options must not turn the entity into a passthrough."""
    select = make_select(0.39)

    await select.async_select_option("not a percentage")

    select._client.set_var.assert_not_called()
