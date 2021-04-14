import pcvs

class GenericException:
    class AlreadyExistError(Exception): pass
    class UnclassifiableError(Exception): pass
    class NotFoundError(Exception): pass
    
class BankException(GenericException):
    pass

class ConfigException(GenericException):
    class BadTokenError(Exception): pass

class ProfileException(GenericException):
    class BadTokenError(Exception): pass

class ValidationException(GenericException):
    class FormatError(Exception): pass
    class SchemeError(Exception): pass

class RunException:
    class OverrideError(Exception): pass
    class InvalidProgramError(Exception): pass
    
class TestException:
    pass
