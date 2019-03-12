class ReqCounter:
    def __init__(self):
        self.counter = 0

    def count(self):
        self.counter += 1

    def get_total(self):
        return self.counter

    def flash(self):
        self.counter = 0
