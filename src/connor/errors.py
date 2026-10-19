class ConnorError(Exception):
    pass


class ConfigError(ConnorError):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("\n".join(problems))
        self.problems = problems


class SchemeError(ConnorError):
    pass


class JournalError(ConnorError):
    pass


class ModelError(ConnorError):
    pass


class PlanError(ConnorError):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("\n".join(problems))
        self.problems = problems
