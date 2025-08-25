import os, time, logging
from typing import Any, Dict, List

def get_env(name: str, required: bool=True, default: str|None=None) -> str:
    val = os.getenv(name, default)
    if required and not val:
        raise RuntimeError(f"Missing environment variable: {name}")
    return val

def setup_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL","INFO"),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

def retry(times:int=3, delay:float=1.5):
    def deco(fn):
        def wrapper(*args, **kwargs):
            last = None
            for i in range(times):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last = e
                    time.sleep(delay * (i+1))
            raise last
        return wrapper
    return deco
