def run_in_coroutine(event_loop, task):
    return event_loop.run_until_complete(task)
