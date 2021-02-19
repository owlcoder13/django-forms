class DynamicObject(object):
    """ model with all existing properties """

    def __hasattr__(self):
        return True

    def __init__(self):
        self.attributes = dict()

    def __setattr__(self, key, value):
        if key != 'attributes':
            self.attributes[key] = value

        super(DynamicObject, self).__setattr__(key, value)

    def __getattr__(self, name):
        return self.attributes[name] if name in self.attributes else None

    def save(self):
        pass
