"""A configuration dictionary with additional feature."""

from typing import Any


class Config(dict):
    """
    A 'Config' is a dict used to manage all configuration fields.

    While it can contain arbitrary data, the whole PCVS
    configuration is composed of 5 distinct 'categories', each being a single
    Config. These are then gathered in a :class:`~pcvs.backend.metaconfig.MetaConfig` object.
    """

    def __init__(self, d: dict | None = None):
        """
        Init the object.

        :param d: items of the configuration
        """
        if d is None:
            d = {}
        super().__init__(**d)

    # recursive exportation to pure python dict for ruyaml representer
    @classmethod
    def __to_dict(cls, d: dict[str, Any]) -> dict[str, Any]:
        for k, v in d.items():
            if isinstance(v, dict):  # is MetaConfig or v is Config:
                d[k] = Config.__to_dict(v)
        return dict(d)

    def to_dict(self) -> dict[str, Any]:
        """Convert the Config() to regular dict."""
        return Config.__to_dict(self)

    # Additional dict functions
    def set_ifdef(self, k: str, v: Any) -> None:
        """
        Shortcut function: init self[k] only if v is not None.

        :param k: name of value to add
        :param v: value to add
        """
        if v is not None:
            self[k] = v
