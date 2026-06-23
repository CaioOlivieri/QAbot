from unittest.mock import patch

import qabot.__main__ as main_mod


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
