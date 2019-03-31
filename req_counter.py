class ReqCounter:
    counter = 0

    @classmethod
    def add(cls):
        cls.counter += 1

    @classmethod
    def get_total(cls):
        return cls.counter

    @classmethod
    def flush(cls):
        cls.counter = 0
