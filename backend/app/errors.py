class BackgroundRemovalError(RuntimeError):
    """Base class for errors that are safe to expose as a generic API failure."""


class ModelNotInstalledError(BackgroundRemovalError):
    """Raised when local BiRefNet files have not been downloaded yet."""
