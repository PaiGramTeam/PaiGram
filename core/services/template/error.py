class TemplateException(Exception):
    pass


class QuerySelectorNotFound(TemplateException):
    pass


class ErrorFileType(TemplateException):
    pass


class FileIdNotFound(TemplateException):
    pass
