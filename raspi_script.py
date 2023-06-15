import asyncio
import nest_asyncio
from demo.runners import alice
from utils import get_agent_endpoint

nest_asyncio.apply()

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)


def start_agent():
    loop.run_until_complete(alice.runAgent(get_agent_endpoint()))


if __name__ == "__main__":
    start_agent()
