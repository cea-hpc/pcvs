class GenericException(Exception):
    """Generic error (custom errors will inherit of this)."""

    def __init__(self, reason="Unkown error",
                 help_msg="Please check pcvs --help for more information.",
                 dbg_info={}):
        """Constructor for generic errors.
        :param *args: unused
        :param **kwargs: messages for the error.
        """
        self._help_msg = help_msg
        self._dbg_info = dbg_info
        super().__init__("{} - {}".format(type(self).__name__, reason))
        
    def __str__(self):
        """Stringify an exception for pretty-printing.

        :return: the string.
        :type: str"""
        dbg_str = ""
        if self._dbg_info:
            dbg_str = "\n\nAdditional notes:\n" + self.dbg_str
        return "{}\n{}{}".format(
            super().__str__(),
            self._help_msg,
            dbg_str
        )

    @property
    def err(self):
        """returns the error part of the exceptions.

        :return: only the error part
        :rtype: str"""
        return str(self)
    
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

    def add_dbg(self, **kwargs):
        for k, v in kwargs.items():
            if k not in self._dbg_info:
                self._dbg_info[k] = v

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
    class NotPCVSRelated(GenericException):
        pass

    class AlreadyExistError(GenericException):
        """The content already exist as it should."""

        def __init__(self, reason="Already Exist", **kwargs):
            """Updated constructor"""
            super().__init__(reason=reason,
                             help_msg="\n".join([
                                 "Note configuration, profiles & pcvs.* files can be ",
                                 "verified through `pcvs check [-c|-p|-D <path>]`"]),
                             dbg_info=kwargs)

    class UnclassifiableError(GenericException):
        """Unable to classify this common error."""
        pass

    class NotFoundError(GenericException):
        """Content haven't been found based on specifications."""
        pass

    class IOError(GenericException):
        """Communication error (FS, process) while processing data."""
        pass

    class BadTokenError(GenericException):
        """Badly formatted string, unable to parse."""
        pass

    class WIPError(GenericException):
        """Work in Progress, not a real error."""
        pass

    class TimeoutError(GenericException):
        """The parent class timeout error."""
        pass

    class NotImplementedError(GenericException):
        """Missing implementation for this particular feature."""
        pass


class BankException(CommonException):
    "Bank-specific exceptions."""
    class ProjectNameError(GenericException):
        """name is not a valid project under the given bank."""
        pass


class ConfigException(CommonException):
    """Config-specific exceptions."""
    pass


class ProfileException(CommonException):
    """Profile-specific exceptions."""

    class IncompleteError(GenericException):
        """A configuration block is missing to build the profile."""
        pass


class ValidationException(CommonException):
    """Validation-specific exceptions."""

    class FormatError(GenericException):
        """The content does not comply the required format (schemes)."""
        def __init__(self, reason="Invalid format", **kwargs):
            """Updated constructor"""
            super().__init__(reason=reason,
                             help_msg="\n".join([
                                 "Input files may be checked with `pcvs check`"]),
                             dbg_info=kwargs)
            
    class WrongTokenError(GenericException):
        """A unknown token is found in valided content"""

        def __init__(self, reason="Invalid token(s) used as Placeholders", **kwargs):
            """Updated constructor"""
            super().__init__(reason=reason,
                             help_msg="\n".join([
                                 "A list of valid tokens is available in the documentation"]),
                             dbg_info=kwargs)

    class SchemeError(GenericException):
        """The content is not a valid format (scheme)."""

        def __init__(self, reason="Invalid Scheme provided", **kwargs):
            """Updated constructor"""
            super().__init__(reason=reason,
                             help_msg="\n".join([
                                 "Provided schemes should be static. If code haven't be",
                                 "changed, please report this error."]),
                             dbg_info=kwargs)


class RunException(CommonException):
    """Run-specific exceptions."""

    class InProgressError(GenericException):
        """A run is currently occuring in the given dir."""

        def __init__(self, reason="Build directory currently used by another instance", **kwargs):
            """Updated constructor"""
            super().__init__(reason=reason,
                             help_msg="\n".join([
                                 "Please Wait for previous executions to complete.",
                                 "You may also use --override or --output to change default build directory"]),
                             dbg_info=kwargs)

    class NonZeroSetupScript(GenericException):
        """a setup script (=pcvs.setup) completed but returned non-zero exit code."""

        def __init__(self, reason="A setup script failed to complete", **kwargs):
            """Updated constructor"""
            super().__init__(reason=reason,
                             help_msg="\n".join([
                                 "Try to run manually the setup script below."]),
                             dbg_info=kwargs)

    class ProgramError(GenericException):
        """The given program cannot be found."""

        def __init__(self, reason="A program cannot be found", **kwargs):
            """Updated constructor"""
            super().__init__(reason=reason,
                             help_msg="\n".join([
                                 "A program/binary defined in loaded profile cannot",
                                 "be found in $PATH or spack/module. Please report",
                                 "if this is a false warning."]),
                             dbg_info=kwargs)


class TestException(CommonException):
    """Test-specific exceptions."""

    class TestExpressionError(GenericException):
        """Test description is wrongly formatted."""

        def __init__(self, reason="Issue(s) while parsing a Test Descriptor", **kwargs):
            """Updated constructor"""
            super().__init__(reason=reason,
                             help_msg="\n".join([
                                 "Please check input files with `pcvs check`"]),
                             dbg_info=kwargs)


class OrchestratorException(CommonException):
    """Execution-specific errors."""

    class UndefDependencyError(GenericException):
        """Declared job dep cannot be fully qualified, not defined."""
        pass

    class CircularDependencyError(GenericException):
        """Circular dep detected while processing job dep tree."""
        pass

class RunnerException(CommonException):
    class LaunchError(GenericException):
        """Unable to run a remote container"""
        pass
    
class PublisherException(CommonException):
    class BadMagicTokenError(GenericException):
        """Issue with token stored to file to check consistency"""
        pass

    class UnknownJobError(GenericException):
        """Unable to identify a job by its ID"""
        pass
    
    class AlreadyExistJobError(GenericException):
        """A single ID leads to multiple jobs."""
        pass
        

class LockException(CommonException):
    """Lock-specific exceptions."""

    class BadOwnerError(GenericException):
        """Attempt to manipulate the lock while the current process is not the
        owner."""
        pass

    class TimeoutError(GenericException):
        """Timeout reached before lock."""
        pass


class PluginException(CommonException):
    """Plugin-related exceptions."""

    class BadStepError(GenericException):
        """targeted pass does not exist."""
        pass

    class LoadError(GenericException):
        """Unable to load plugin directory."""
        def __init__(self, reason="Issue(s) while loading plugin", **kwargs):
            """Updated constructor"""
            super().__init__(reason=reason,
                             help_msg="\n".join([
                                 "Please ensure plugins can be imported like:",
                                 "python3 ./path/to/plugin/file.py"]),
                             dbg_info=kwargs)


class GitException(CommonException):
    class BadEntryError(GenericException):
        pass

