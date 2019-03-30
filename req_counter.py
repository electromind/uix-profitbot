class ReqCounter:
    def __init__(self):
        self.counter = 0

    def add(self):
        self.counter += 1

    def get_total(self):
        return self.counter

    def flush(self):
        self.counter = 0
