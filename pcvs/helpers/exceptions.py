class GenericError(Exception):
    """Generic error (custom errors will inherit of this)."""

    def __init__(self, msg, **kwargs):
        """Constructor for generic errors.
        :param *args: unused
        :param **kwargs: messages for the error.
        """
        message = "{}".format(msg)
        for k, v in kwargs.items():
            message += "\n- {}: {}".format(k, v)
        
        super().__init__(message)


class CommonException:
    """Gathers exceptions commonly encountered by more specific namespaces."""

    class AlreadyExistError(GenericError):
        """The content already exist as it should."""

        pass

    class UnclassifiableError(GenericError):
        """Unable to classify this common error."""

        pass

    class NotFoundError(GenericError):
        """Content haven't been found based on specifications."""

        pass

    class IOError(GenericError):
        """Communication error (FS, process) while processing data."""

        pass

    class BadTokenError(GenericError):
        """Badly formatted string, unable to parse."""

        pass

    class WIPError(GenericError):
        """Work in Progress, not a real error."""

        pass
    
    class NotImplementedError(GenericError):
        """Missing implementation for this particular feature."""


class BankException(CommonException):
    "Bank-specific exceptions."""
    class ProjectNameError(GenericError):
        """name is not a valid project under the given bank."""
        pass


class ConfigException(CommonException):
    """Config-specific exceptions."""

    pass


class ProfileException(CommonException):
    """Profile-specific exceptions."""

    class IncompleteError(GenericError):
        """A configuration block is missing to build the profile."""

        pass


class ValidationException(CommonException):
    """Validation-specific exceptions."""

    class FormatError(GenericError):
        """The content does not comply the required format (schemes)."""

        pass

    class SchemeError(GenericError):
        """The content is not a valid format (scheme)."""

        pass


class RunException(CommonException):
    """Run-specific exceptions."""

    class OverrideError(GenericError):
        """A previous run exist and the override permission haven't be given."""

        pass

    class InProgressError(GenericError):
        """A run is currently occuring in the given dir."""

        pass

    class ProgramError(GenericError):
        """The given program cannot be found."""

        pass

    class TestUnfoldError(GenericError):
        """Issue raised during processing test files."""

        pass


class TestException(CommonException):
    """Test-specific exceptions."""

    class TDFormatError(GenericError):
        """Test description is wrongly formatted."""

        pass

    class DynamicProcessError(GenericError):
        """Test File is not properly formatted."""
        pass


class OrchestratorException(CommonException):
    """Execution-specific errors."""

    class UndefDependencyError(GenericError):
        """Declared job dep cannot be fully qualified, not defined."""

        pass

    class CircularDependencyError(GenericError):
        """Circular dep detected while processing job dep tree."""

        pass


class LockException(CommonException):
    """Lock-specific exceptions."""

    class BadOwnerError(GenericError):
        """Attempt to manipulate the lock while the current process is not the
        owner."""
        pass

    class TimeoutError(GenericError):
        """Timeout reached before lock."""
        pass
    

class PluginException(CommonException):
    """Plugin-related exceptions."""
    
    class BadStepError(GenericError):
        """targeted pass does not exist."""
        pass
    
    class LoadError(GenericError):
        """Unable to load plugin directory."""
        pass