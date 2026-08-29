class CloudForgeError(Exception):
    """Base exception for CloudForge analysis errors."""


class RepositoryNotFoundError(CloudForgeError):
    pass


class UnsupportedManifestError(CloudForgeError):
    pass


class ManifestParseError(CloudForgeError):
    pass


class AnalysisWarning(CloudForgeError):
    pass
