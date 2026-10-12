import subprocess
import sys


def test_memory_import_does_not_eagerly_load_llm_agents():
    # Use a fresh interpreter because the wider suite also exercises the legacy
    # graph and may legitimately load agent modules before this test runs.
    code = (
        "from tradingagents.agents.utils.memory import TradingMemoryLog; "
        "import sys; assert TradingMemoryLog is not None; "
        "assert 'tradingagents.agents.analysts.market_analyst' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
