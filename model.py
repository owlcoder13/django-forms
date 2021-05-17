import json


class DynamicObject(object):
    """ model with all existing properties """

    def __hasattr__(self):
        return True

    def __init__(self):
        self._attrs = dict()

    def __setattr__(self, key, value):
        if key != '_attrs':
            self._attrs[key] = value

        super(DynamicObject, self).__setattr__(key, value)

    def __getattr__(self, key):
        if key != '_attrs':
            return self._attrs[key] if key in self._attrs else None

        super(DynamicObject, self).__getattr__(key)

    def save(self):
        pass

    @classmethod
    def from_json(cls, text):

        if text is None:
            return cls()

        try:
            d = json.loads(text)
        except json.JSONDecodeError:
            return cls()

        return cls.from_any(d)

    @classmethod
    def from_any(cls, input):
        if input is None:
            return None

        if isinstance(input, list):  # if list dive deeper recursive
            return [cls.from_any(a) for a in input]

        a = cls()

        for key, value in input.items():
            if isinstance(value, dict) or isinstance(value, list):
                setattr(a, key, cls.from_any(value))  # dive deeper
            else:
                setattr(a, key, value)

        return a

    def to_dict(self):
        out = dict()

        for a, v in self._attrs.items():
            if isinstance(v, list):
                out[a] = [a.to_dict() for a in v]
            elif isinstance(v, DynamicObject):
                out[a] = v.to_dict()
            else:
                out[a] = v

        return out
