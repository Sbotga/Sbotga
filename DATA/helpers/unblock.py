"""
Run blocking operations safely.
"""

import asyncio
from typing import Callable, Any
from concurrent.futures import ThreadPoolExecutor
import threading

executor = ThreadPoolExecutor(max_workers=64)


def to_thread(func: Callable, *args, **kwargs):
    threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True).start()


async def to_process_with_timeout(
    func: Callable, *args: Any, timeout: int = 20, **kwargs: Any
) -> Any:
    """
    Runs a function in a separate thread with a timeout option.

    Parameters:
    - func (Callable): The function to run.
    - *args (Any): Positional arguments for the function.
    - timeout (int, optional): Timeout in seconds. If None, waits indefinitely.
    - **kwargs (Any): Keyword arguments for the function.

    Returns:
    - Any: The result of the function if it completes within the timeout.

    Raises:
    - TimeoutError: If the function does not complete within the timeout.
    """
    loop = asyncio.get_running_loop()
    try:
        # Run the function in the ThreadPoolExecutor with a timeout
        return await asyncio.wait_for(
            loop.run_in_executor(executor, lambda: func(*args, **kwargs)),
            timeout,
        )
    except asyncio.TimeoutError:
        raise TimeoutError(
            f"Function {func.__name__} timed out after {timeout} seconds"
        )
