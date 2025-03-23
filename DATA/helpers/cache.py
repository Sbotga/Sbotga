__all__ = ("CACHE",)


class _Singleton:
    def __init__(self):
        self._store = {}

    def __getitem__(self, key):
        return self._store[key]

    def __setitem__(self, key, value):
        self._store[key] = value

    def __getattr__(self, key):
        if key in self._store:
            return self._store[key]
        raise AttributeError(f"The CACHE has no cached value '{key}'")

    def __setattr__(self, key, value):
        if key == "_store":
            super().__setattr__(key, value)
        else:
            self._store[key] = value


CACHE = _Singleton()
