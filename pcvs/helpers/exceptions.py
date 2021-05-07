# use this class as a template
class GenericError(Exception): pass

class CommonException:
    class AlreadyExistError(GenericError): pass
    class UnclassifiableError(GenericError): pass
    class NotFoundError(GenericError): pass
    class IOError(GenericError): pass
    class BadTokenError(GenericError): pass
    class WIPError(GenericError): pass

    
class BankException(CommonException): pass

class ConfigException(CommonException): pass
    
class ProfileException(CommonException):
    class BadTokenError(GenericError): pass
    class IncompleteError(GenericError): pass

class ValidationException(CommonException):
    class FormatError(GenericError): pass
    class SchemeError(GenericError): pass

class RunException(CommonException):
    class OverrideError(GenericError): pass
    class InProgressError(GenericError): pass
    class ProgramError(GenericError): pass
    class TestUnfoldError(GenericError): pass
    
class TestException(CommonException):
    class TDFormatError(GenericError): pass

class OrchestratorException(CommonException):
    class UndefDependencyError(GenericError): pass
    class CircularDependencyError(GenericError): pass
    
class LockException(CommonException):
    class BadOwnerError(GenericError): pass
    class TimeoutError(GenericError): pass