class MirrorError(Exception):
    """Base typed exception for MIRROR."""


class KrakenCliNotInstalled(MirrorError):
    pass


class KrakenCliCommandFailed(MirrorError):
    pass


class KrakenNotPaperMode(MirrorError):
    pass


class KrakenSymbolDiscoveryFailed(MirrorError):
    pass


class InferenceRateLimited(MirrorError):
    pass


class InferenceMalformedJSON(MirrorError):
    pass


class PatchValidationFailed(MirrorError):
    pass


class HoldoutGateFailed(MirrorError):
    pass


class ChainTransactionFailed(MirrorError):
    pass


class IPFSPinningFailed(MirrorError):
    pass

