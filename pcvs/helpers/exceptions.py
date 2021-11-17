class GenericError(Exception):
    """Generic error (custom errors will inherit of this)."""

    def __init__(self, err_msg="Unkown error",
                 help_msg="Please check pcvs --help for more information.",
                 dbg_info={}):
        """Constructor for generic errors.
        :param *args: unused
        :param **kwargs: messages for the error.
        """
        self._err_msg = "{} - {}".format(type(self).__name__, err_msg)
        self._help_msg = help_msg
        self._dbg_info = dbg_info

    def __str__(self):
        """Stringify an exception for pretty-printing.

        :return: the string.
        :type: str"""
        dbg_str = ""
        if self._dbg_info:
            dbg_str = "\n\nExtra infos:\n" + self.dbg_str
        return "{}\n{}{}".format(
            self._err_msg,
            self._help_msg,
            dbg_str
        )

    @property
    def err(self):
        """returns the error part of the exceptions.

        :return: only the error part
        :rtype: str"""
        return self._err_msg

    @property
    def help(self):
        """returns the help part of the exceptions.

        :return: only the help part
        :rtype: str"""
        return self._help_msg

    @property
    def dbg(self):
        """returns the extra infos of the exceptions (if any).

        :return: only the debug infos.
        :rtype: str"""
        return self._dbg_info

    @property
    def dbg_str(self):
        """Stringify the debug infos. These infos are stored as a dict
initially.

        :return: a itemized string.
        :rtype: str"""
        if not self._dbg_info:
            return " - None"
        w = max([len(k) for k in self._dbg_info.keys()])
        return "\n".join([" - {:<{w}}: {}".format(k, v, w=w) for k, v in self._dbg_info.items()])


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

    class TimeoutError(GenericError):
        """The parent class timeout error."""
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

        def __init__(self, msg="Invalid format", **kwargs):
            """Updated constructor"""
            super().__init__(err_msg=msg,
                             help_msg="\n".join([
                                 "Note configuration, profiles & pcvs.* files can be ",
                                 "verified through `pcvs check [-c|-p|-D <path>]`"]),
                             dbg_info=kwargs)

    class SchemeError(GenericError):
        """The content is not a valid format (scheme)."""

        def __init__(self, msg="Invalid Scheme provided", **kwargs):
            """Updated constructor"""
            super().__init__(err_msg=msg,
                             help_msg="\n".join([
                                 "Provided schemes should be static. If code haven't be",
                                 "changed, please report this error."]),
                             dbg_info=kwargs)


class RunException(CommonException):
    """Run-specific exceptions."""

    class InProgressError(GenericError):
        """A run is currently occuring in the given dir."""

        def __init__(self, msg="Execution in progress in this build directory", **kwargs):
            """Updated constructor"""
            super().__init__(err_msg=msg,
                             help_msg="\n".join([
                                 "Please Wait for previous executions to complete.",
                                 "You may also use --override or --output to change",
                                 "the default build directory path"]),
                             dbg_info=kwargs)

    class ProgramError(GenericError):
        """The given program cannot be found."""

        def __init__(self, msg="Program cannot be found", **kwargs):
            """Updated constructor"""
            super().__init__(err_msg=msg,
                             help_msg="\n".join([
                                 "A program/binary defined in loaded profile cannot",
                                 "be found in $PATH or spack/module. Please report",
                                 "if this is a false warning."]),
                             dbg_info=kwargs)

    class TestUnfoldError(GenericError):
        """Issue raised during processing test files."""

        def __init__(self, msg="Issue(s) while parsing test input", **kwargs):
            """Updated constructor"""
            super().__init__(err_msg=msg,
                             help_msg="\n".join([
                                 "Test directories can be checked beforehand with `pcvs check -D <path>`",
                                 "See pcvs check --help for more information."]),
                             dbg_info=kwargs)


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
