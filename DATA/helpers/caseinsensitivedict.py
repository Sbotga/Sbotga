import json


class CaseInsensitiveDict(dict):
    @classmethod
    def _k(cls, key):
        return key.lower() if isinstance(key, str) else key

    def __init__(self, *args, **kwargs):
        self._store = {}
        self._del = False
        try:
            super(CaseInsensitiveDict, self).__init__(*args, **kwargs)
        except ValueError:
            args = list(args)
            args[0] = json.loads(args[0])
            args = tuple(args)
            super(CaseInsensitiveDict, self).__init__(*args, **kwargs)
        self._convert_keys()

    def __getitem__(self, key):
        return super(CaseInsensitiveDict, self).__getitem__(self.__class__._k(key))

    def __setitem__(self, key, value):
        super(CaseInsensitiveDict, self).__setitem__(self.__class__._k(key), value)
        self._store[self._k(key)] = key

    def __delitem__(self, key):
        del self._store[self._k(key)]
        return super(CaseInsensitiveDict, self).__delitem__(self.__class__._k(key))

    def __contains__(self, key):
        return super(CaseInsensitiveDict, self).__contains__(self.__class__._k(key))

    def has_key(self, key):
        return super(CaseInsensitiveDict, self).has_key(self.__class__._k(key))

    def pop(self, key, *args, **kwargs):
        key_lower = self._k(key)
        if key_lower in self._store and self._del:
            del self._store[key_lower]
        return super(CaseInsensitiveDict, self).pop(
            self.__class__._k(key), *args, **kwargs
        )

    def get(self, key, *args, **kwargs):
        return super(CaseInsensitiveDict, self).get(
            self.__class__._k(key), *args, **kwargs
        )

    def get_key(self, key):
        return self._store.get(self.__class__._k(key))

    def setdefault(self, key, *args, **kwargs):
        key_lower = self._k(key)
        if key_lower not in self._store:
            self._store[key_lower] = key
        return super(CaseInsensitiveDict, self).setdefault(
            self.__class__._k(key), *args, **kwargs
        )

    def update(self, E={}, **F):
        super(CaseInsensitiveDict, self).update(self.__class__(E))
        super(CaseInsensitiveDict, self).update(self.__class__(**F))

    def _convert_keys(self):
        {key.lower(): key for key in self.keys()}
        for k in list(self.keys()):
            v = super(CaseInsensitiveDict, self).pop(k)
            self.__setitem__(k, v)
        self._del = True

    def keys(self):
        if self._del:
            return self._store.values()
        else:
            return super(CaseInsensitiveDict, self).keys()

    def items(self):
        return [(self._store[key.lower()], self[key]) for key in self]

    def __str__(self):
        return (
            "{"
            + ", ".join(f"'{self._store[key.lower()]}': {self[key]}" for key in self)
            + "}"
        )

    def __repr__(self):
        return f"CaseInsensitiveDict({str(self)})"
