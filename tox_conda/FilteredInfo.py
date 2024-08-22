"""
https://github.com/masenf/tox-ignore-env-name-mismatch

MIT License
Copyright (c) 2023 Masen Furer
"""

from contextlib import contextmanager
from typing import Any, Iterator, Optional, Sequence, Tuple

from tox.tox_env.info import Info


class FilteredInfo(Info):
    """Subclass of Info that optionally filters specific keys during compare()."""

    def __init__(
        self,
        *args: Any,
        filter_keys: Optional[Sequence[str]] = None,
        filter_section: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        :param filter_keys: key names to pop from value
        :param filter_section: if specified, only pop filter_keys when the compared section matches

        All other args and kwargs are passed to super().__init__
        """
        self.filter_keys = filter_keys
        self.filter_section = filter_section
        super().__init__(*args, **kwargs)

    @contextmanager
    def compare(
        self,
        value: Any,
        section: str,
        sub_section: Optional[str] = None,
    ) -> Iterator[Tuple[bool, Optional[Any]]]:
        """Perform comparison and update cached info after filtering `value`."""
        if self.filter_section is None or section == self.filter_section:
            try:
                value = value.copy()
            except AttributeError:  # pragma: no cover
                pass
            else:
                for fkey in self.filter_keys or []:
                    value.pop(fkey, None)
        with super().compare(value, section, sub_section) as rv:
            yield rv
