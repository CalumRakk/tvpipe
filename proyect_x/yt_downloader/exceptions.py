class QualityNotFoundError(Exception):
    def __init__(self, msg, code_error=-1):
        super().__init__(msg)
        self.code_error = code_error

    def __str__(self):
        return f"[Error {self.code_error}] {self.args[0]}"


class ScheduleNotFound(Exception):
    def __init__(self, msg, code_error=-1):
        super().__init__(msg)
        self.code_error = code_error
