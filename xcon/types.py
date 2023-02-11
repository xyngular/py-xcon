from typing import Dict, Any
from xsentinels.default import DefaultType
from typing import Dict, Union, Type, TypeVar


T = TypeVar('T')

JsonDict = Dict[str, Any]

# todo: Put my `OrderedSet` class into library and use that instead.
OrderedSet = Dict[T, Type[None]]
"""
Internally we are using a dict as an ordered-set; python 3.7 guarantees dicts
keep their insertion order. So these are ordered sets of values inside a dict.
They can also have the Default value as one of their values. It's replaced by
the parent's values when resolved/used.

.. todo:: Perhaps make an OrderedSet as a dict-subclass, with a few extra nice set-based methods?
"""

OrderedDefaultSet = OrderedSet[Union[T, DefaultType]]
"""
Same as `OrderedSet`, except it adds in a `Default` for use as well. It's common internally
in `xynlib.config.config.Config` to use this type. Might be useful elsewhere.
The `Default` type is mean to be used to say 'insert default stuff where this placeholder is at'.
"""
