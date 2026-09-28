from lite6.gamepad import Gamepad, parse_hid_report, shape


def test_shape_deadzone_and_curve():
    assert shape(0.05) == 0.0  # inside the deadzone: no drift
    assert shape(0.5) == 0.25  # squared: half push = quarter speed
    assert shape(-1.0) == -1.0  # full push keeps its sign
    assert shape(1.3) == 1.0  # clipped


def test_hid_report():
    # left stick right + up, right stick down, d-pad up, R1 held
    state, held = parse_hid_report(bytes([255, 0, 128, 128, 255, 0, 0b10, 0]))
    assert state.left_x == 1.0 and state.left_y > 0.99 and state.right_y == -1.0
    assert state.dpad == (0, 1)
    assert held == {"close"}


def test_button_counts_once_while_held():
    pad = Gamepad.__new__(Gamepad)  # skip opening real hardware
    pad._held = set()
    pad._read_raw = lambda: parse_hid_report(bytes([128, 128, 128, 128, 128, 15, 0b1, 0]))
    assert pad.read().pressed == {"open"}
    assert pad.read().pressed == set()
