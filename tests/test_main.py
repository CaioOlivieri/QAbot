from unittest.mock import patch

import qabot.__main__ as main_mod
from qabot.agent.smoke import SmokeResult


def test_main_without_args_prints_usage_and_returns_1(capsys) -> None:
    with patch.object(main_mod.sys, "argv", ["qabot"]):
        rc = main_mod.main()
    assert rc == 1
    assert "Usage" in capsys.readouterr().out


def test_main_runs_agent_and_prints_result(capsys) -> None:
    with patch.object(main_mod.sys, "argv", ["qabot", "/proj"]):
        with patch.object(main_mod, "run_agent", return_value="done") as run_agent:
            rc = main_mod.main()
    run_agent.assert_called_once_with("/proj")
    assert rc == 0
    assert "done" in capsys.readouterr().out


def test_smoke_tier_pass_returns_0(capsys) -> None:
    passing = SmokeResult("PASS", [], "# report", {})
    with patch.object(main_mod.sys, "argv", ["qabot", "/proj", "--tier", "smoke"]):
        with patch.object(main_mod, "run_smoke", return_value=passing) as run_smoke:
            rc = main_mod.main()
    run_smoke.assert_called_once_with("/proj", source_dir=None)
    assert rc == 0
    assert "Gate: PASS" in capsys.readouterr().out


def test_smoke_tier_fail_returns_1_with_reasons(capsys) -> None:
    failing = SmokeResult("FAIL", ["coverage 50.0% ≤ 80%"], "# report", {})
    argv = ["qabot", "/proj", "--tier", "smoke", "--source", "qabot"]
    with patch.object(main_mod.sys, "argv", argv):
        with patch.object(main_mod, "run_smoke", return_value=failing) as run_smoke:
            rc = main_mod.main()
    run_smoke.assert_called_once_with("/proj", source_dir="qabot")
    assert rc == 1
    out = capsys.readouterr().out
    assert "Gate: FAIL" in out
    assert "coverage 50.0%" in out
