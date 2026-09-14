class ConduitError(Exception):
    def __init__(self, code, message):
        super().__init__(f"[{code}] {message}" if code else message)
        self.code = code
        self.message = message


class TopicNotFound(ConduitError):
    pass


class TopicNotActive(ConduitError):
    pass


class AppNotFoundOrRevoked(ConduitError):
    pass


class AppCannotProduce(ConduitError):
    pass


class SchemaViolation(ConduitError):
    pass


class MessageTooLarge(ConduitError):
    pass


class GroupNotFoundOrPaused(ConduitError):
    pass


class NotSubscribed(ConduitError):
    pass


class NoPartitions(ConduitError):
    pass


class UnknownRole(ConduitError):
    pass


class UnknownUser(ConduitError):
    pass


class InvalidPartitionCount(ConduitError):
    pass


class DlqNotPending(ConduitError):
    pass


class InvalidStatusValue(ConduitError):
    pass


class PartitionConflict(ConduitError):
    pass


class ProduceDenied(ConduitError):
    pass


class ConsumeDenied(ConduitError):
    pass


class OffsetRegression(ConduitError):
    pass


class InvalidApiKey(ConduitError):
    pass


class AccessDenied(ConduitError):
    pass


class DuplicateKey(ConduitError):
    pass


_MAP = {
    "CDT01": TopicNotFound,
    "CDT02": TopicNotActive,
    "CDT03": AppNotFoundOrRevoked,
    "CDT04": SchemaViolation,
    "CDT05": MessageTooLarge,
    "CDT06": GroupNotFoundOrPaused,
    "CDT07": NotSubscribed,
    "CDT09": NoPartitions,
    "CDT11": UnknownRole,
    "CDT12": UnknownUser,
    "CDT13": InvalidPartitionCount,
    "CDT14": DlqNotPending,
    "CDT15": InvalidStatusValue,
    "CDT16": PartitionConflict,
    "CDT17": ProduceDenied,
    "CDT18": ConsumeDenied,
    "CDT19": OffsetRegression,
    "CDT20": AppCannotProduce,
    "CDT22": InvalidApiKey,
}


def from_psycopg(exc):
    code = getattr(exc, "sqlstate", None) or ""
    text = str(exc) or exc.__class__.__name__
    message = text.splitlines()[0]
    if code in _MAP:
        return _MAP[code](code, message)
    if code == "42501":
        return AccessDenied(code, message)
    if code == "23505":
        return DuplicateKey(code, message)
    return ConduitError(code, message)
