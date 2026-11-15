"""Project exceptions. None of these carry API secrets."""


class AtlasError(Exception):
    """Base error for expected operational failures."""


class AdapterError(AtlasError):
    """Market-data request failed."""


class AdapterUnavailable(AdapterError):
    """Adapter exists but cannot serve data in this version or environment."""


class DataError(AtlasError):
    """Candle or ticker payload failed validation."""


class CredentialsMissing(AtlasError):
    """An optional credential is absent. Public data calls should not raise this."""


class LiveTradingDisabled(AtlasError):
    """Live order routing is not implemented."""
