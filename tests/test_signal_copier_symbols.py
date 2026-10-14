from signal_copier.symbols import resolve

FTMO = ["EURUSD", "GBPUSD", "XAUUSD", "US100.cash", "US30.cash", "GER40.cash", "USOIL.cash"]
SUFFIX_S = ["EURUSD.s", "GBPUSD.s", "XAUUSD.s", "NAS100.s"]
GLUED = ["EURUSDm", "GBPUSDm", "XAUUSDm", "USTECm"]


def test_ftmo_names():
    assert resolve("EURUSD", FTMO) == "EURUSD"
    assert resolve("NAS100", FTMO) == "US100.cash"
    assert resolve("US30", FTMO) == "US30.cash"


def test_dot_suffix():
    assert resolve("GBPUSD", SUFFIX_S) == "GBPUSD.s"
    assert resolve("NAS100", SUFFIX_S) == "NAS100.s"


def test_glued_suffix():
    assert resolve("XAUUSD", GLUED) == "XAUUSDm"
    assert resolve("NAS100", GLUED) == "USTECm"


def test_two_candidates_is_no_guess():
    assert resolve("EURUSD", ["EURUSD.s", "EURUSD.pro"]) is None


def test_unknown_symbol():
    assert resolve("USDJPY", FTMO) is None


def test_override_wins_and_must_exist():
    assert resolve("EURUSD", ["EURUSD.s", "EURUSD.pro"], {"EURUSD": "EURUSD.pro"}) == "EURUSD.pro"
    assert resolve("EURUSD", FTMO, {"EURUSD": "EURUSD.raw"}) is None


# PU Prime demo, tradable names only (2026-10-14). The plain EURUSD there is quote-only.
PUPRIME = ["EURUSD.s", "GBPUSD.s", "NZDUSD.s", "USDCAD.s", "USDJPY.s", "XAUUSD.s",
           "NAS100.s", "NAS100ft.s", "DJ30.s", "GER40.s", "CL-OIL.s", "GASOIL-Cs"]


def test_puprime_names():
    assert resolve("EURUSD", PUPRIME) == "EURUSD.s"
    assert resolve("XAUUSD", PUPRIME) == "XAUUSD.s"
    assert resolve("NAS100", PUPRIME) == "NAS100.s"
    assert resolve("US30", PUPRIME) == "DJ30.s"
    assert resolve("USOIL", PUPRIME) == "CL-OIL.s"
