class TelegramServiceError(Exception):
    """Base exception for telegram service"""


class AuthenticationError(TelegramServiceError):
    """Session invalid or unauthorized"""


class PermissionDeniedError(TelegramServiceError):
    """Bot/User cannot write to the target chat"""
