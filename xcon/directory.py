from __future__ import annotations

import datetime as dt
import string
import weakref
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Union, Dict, Iterable, Mapping, Optional, Tuple

__pdoc__ = {
    "Directory.path": True,
    "DirectoryItem.__repr__": True,
    "DirectoryItem.__str__": True,
}

import ciso8601

from xsentinels import Default
from .types import JsonDict
from xloop import xloop

from xcon.exceptions import ConfigError


@dataclass(eq=True, frozen=True)
class DirectoryChain:
    """ Immutable list of directories, use to provide a hashing ability for list of directories.
    """
    directories: Iterable[Directory] = field(default_factory=tuple, compare=False)
    concatenated_directory_paths: str = field(init=False, compare=True)

    def __post_init__(self):
        # ensure what we get passed in are converted to a tuple of Directory's
        # [in case there are strings, etc]. Ensures we don't have a mutable type
        # in our object [like a list or OrderedSet/dict].
        directories = tuple(Directory.from_path(x) for x in self.directories)
        object.__setattr__(self, 'directories', directories)

        # Pre-calculate a useful field, a concatenated list of the directory paths.
        directory_key_names = []
        for directory in directories:
            directory_key_names.append(directory.path)
        object.__setattr__(self, 'concatenated_directory_paths', '|'.join(directory_key_names))


# Setting frozen/immutable + eq, will also make us hashable with the
# class-attr values automatically!
@dataclass(eq=True, frozen=True)
class Directory:
    """
    Represents a path/directory to search in our various configuration service providers.
    If no 'service' is provided to the '__init__', then we default to the 'global' service.
    If no 'env' is provided, we won't include it in the directory/path.
    """

    # Both Prepopulated in __post_init__(...):
    #   We also use this for compare since it's a single obj and uniquely identifies the directory.
    path: str = field(init=True, default=None, compare=True)
    """ Directory path, this is the fundamental identity for a directory, and is what is used
        to compare it's self to other directories.

        If you provide a service and/or env as part of the init and not a path, we will produce
        the path for you from the service and/or env components.

        you either give an env/service or a path.  THe preferred and faster way to get a directory
        from a path is via `Directory.from_path` class method.  This will lookup the path
        in a cache and try to return a directory that's already in use if possible.

        You can't pass a env/service + path at the same time when creating a Directory, ie:

        >>> Directory(path="/some/path", env="hello", service="there")
        **Exception Raised**
    """

    service: str = field(compare=False, default=Default)
    """ Service part of the directory path. By Default, if no service or path is passed in
        this is set to `global`.
    """

    env: Optional[str] = field(compare=False, default=None)
    """ Environmental part of the directory path, ie: `/some_service/{env}`. If this is None
        (the default) we don't have the environment name in the resulting directory path.
    """

    is_non_existent: bool = field(init=False, default=False, compare=False)
    """ If this directory is the special non-existent directory we use to for non-existent values,
        this will be True.
    """

    is_export: bool = field(init=True, default=False, compare=False)
    """ If this directory is for export values from another service, this is True.
        Example Path:

        /hubspot/export/testing/HUBSPOT_SOME_QUEUE_NAME
    """

    # Setting `hash` to False, because it's very, very unlikely a formatted and unformatted
    # Directory object would ever be in the same set/ordered-set/dict (ie: optimization).
    is_path_format: bool = field(init=True, default=None, compare=True, hash=False)
    """
    If `None` (default): WIll auto-discover if the path is formatted or not and set
    `is_path_format` to True or False depending on what is discovered
    (see if `True` / `False` below for details).

    If `True` (default): Will look for formatting directives, the only two used/looked-for are
    `service` and `environment`.

    You can use them just like you would a normal `f` string; example:

    `"/{service}/{environment}"`

    Don't end the path in a slash.

    When the directory path is resolved while `xcon.config.Config` is lookup up a config value,
    it will format the path for you with the two variables provided.

    You don't have to include both variables, you may only want one in a particular directory
    path (ie: `"/{service}"`); they will simply be available for use as needed to format the
    path.

    If `False`: Won't look for formatting directives when resolving path,
    will use the path `as-is`.
    """

    def __post_init__(self):
        if self.path:
            assert not self.env, "Can't provide a env + path simultaneously to Directory."
            assert not self.service, "Can't provide a service + path simultaneously to Directory."
            service, env = _service_env_from_path(path=self.path)
            object.__setattr__(self, "service", service)
            object.__setattr__(self, "env", env)

        if not self.service:
            # Default service to "global"
            object.__setattr__(self, "service", "global")

        # Calculate the path one time, set it on path-var.
        path = Directory._path_from_components(
            service=self.service,
            environment=self.env,
            is_export=self.is_export
        )
        object.__setattr__(self, 'path', path)

        if path == "/_nonExistent":
            object.__setattr__(self, "is_non_existent", True)

        if not self.is_export:
            env = self.env
            # If we have export in the start of environment name, we override is_export to True.
            if env and (env.startswith("export") or env.startswith("/export")):
                object.__setattr__(self, "is_export", True)

        is_path_format = self.is_path_format
        if is_path_format is None or is_path_format:
            format_keys = {t[1] for t in string.Formatter().parse(path) if t[1] is not None}
            unknown_keys = format_keys - {'service', 'environment'}
            if unknown_keys:
                raise ConfigError(
                    f"Using unknown format keys ({unknown_keys}) for directory path ({path})."
                )

            object.__setattr__(self, "is_path_format", bool(format_keys))

        # init the resolve-cache with dict if we are a format-path:
        object.__setattr__(self, "_resolve_cache", dict() if self.is_path_format else None)

        # Only cache it if it's not already present, we want to try to use a standard
        # Directory object for a particular path as much as possible.
        if path not in _path_to_directory_cache:
            _path_to_directory_cache[path] = self

    @classmethod
    def from_non_existent(cls) -> Directory:
        """
        Gives you back the standard non-existent directory, the standard path used for this is:
        '/_nonExistent'

        The returned directory object will have it's `.is_non_existent` property set to True.
        """
        return cls.from_path("/_nonExistent")

    @classmethod
    def _path_from_components(cls, service: str, environment: str, is_export: bool = False):
        if not service:
            service = 'global'

        path = f'/{service}'

        if environment and environment.startswith("/"):
            # Remove starting slash if needed
            environment = environment[1:]

        # Add 'export' to front if needed.
        if is_export:
            if not environment:
                environment = "export"
            elif not environment.startswith("export/"):
                environment = f"export/{str(environment)}"

        if environment:
            path = f"{path}/{str(environment)}"

        return path

    @classmethod
    def from_components(cls, service: str, environment: str):
        """ This will return a cached copy if we have one, otherwise we create and return it. """
        return cls.from_path(cls._path_from_components(service=service, environment=environment))

    @classmethod
    def from_path(cls, path: Union[DirectoryOrPath, None]) -> Directory:
        """ If path is a Directory:docs/conf.py:77:1
                return passed in Directory object unaltered.
            If path is a str:
                If the Directory for path currently exists [cached], we will intern it to
                that existing object and return it. Otherwise we return a new Directory for path.
            If path is None:
                return None
        """
        if path is None:
            # Python 3.9 will have the ability to say:
            #    "only if we get passed None, we will return None"
            #    for now, we type ourselves as non-optional return, since it's mostly true.
            return None

        if isinstance(path, Directory):
            # Try to intern the value to a standard-version [just a bit more efficient].
            directory = _path_to_directory_cache.get(path.path, path)
            if path is not directory:
                # If we don't have this Directory object in cache, put it in there.
                _path_to_directory_cache[directory.path] = directory
            return directory

        existing_dir = _path_to_directory_cache.get(path)
        if existing_dir:
            return existing_dir

        # elements[0] should be a blank string [it's the part before the first `/`].
        components = _service_env_from_path(path=path)
        return Directory(service=components[0], env=components[1])

    _resolve_cache = None
    """
    Used to cache `resolved` directory results based onfinal formatted service/environment values.
    """

    def resolve(self, service: str, environment: str) -> Directory:
        if not self.is_path_format:
            return self

        if resolved_environs := self._resolve_cache.get(service):
            if resolved := resolved_environs.get(environment):
                return resolved

        unformatted = self.path
        formatted = unformatted.format_map({'service': service, 'environment': environment})
        if formatted == unformatted:
            self._resolve_cache.setdefault(service, {})[environment] = self
            return self

        resolved = Directory(path=formatted, is_path_format=False)
        self._resolve_cache.setdefault(service, {})[environment] = resolved
        return resolved


def _service_env_from_path(path: str) -> Tuple[Optional[str], Optional[str]]:
    """ Takes path and parses out the service and env.
        If the path does not contain some component, uses None.

        Returns:
            Tuple[Optional[str], Optional[str]]: First element is service, second is environment.
    """
    existing_dir = _path_to_directory_cache.get(path)
    if existing_dir:
        return existing_dir.service, existing_dir.env

    # elements[0] should be a blank string [it's the part before the first `/`].
    elements = path.split("/")
    elements_len = len(elements)
    service = elements[1] if elements_len > 1 else None
    env = "/".join(elements[2:]) if elements_len > 2 else None
    return service, env


DirectoryOrPath = Union[Directory, str]
"""
Type used to indicate a `Directory` or a `str` object [can be either].
"""

DirectoryItemValue = Union[JsonDict, list, str, int, None]
""" A type indicating the of values a `DirectoryItem.value` could return.
    Generally, it's either a `xsentinels.JsonDict` or a `list`/`str`/`int`/`None`.
    Basically, the basic str/int in combination with what you generally could store in JSON.
"""


@dataclass(frozen=True, eq=False)
class DirectoryItem:
    """
    An immutable directory item, which associates a name/value pair for a particular directory.
    There is an optional ttl, mostly used with the Dynamo provider, but may be used in the
    future if we decide to start expiring items inside the process [right now we keep any
    values we get inside process for the life-time of the process].

    Create a new director-item.

    Args:
        name: Will be converted to a str if needed, and lower-cased and then set on self.
            Sets what self.name will return.

        directory: .
            If a string will lookup via `Directory.from_path(directory)` for you automatically.

            If `directory` == None, will use `Directory.from_non_existent()` as the directory;
            you can ask directory object if it's non-existent via `.is_non_existent` property.

            Sets what self.directory will return.

        value: Sets self.value to this.

        source: Generally set to the name of the provider, the DynamoCacher sets this to the
            original item's source + directory path.

        ttl: Used mainly for dynamo. It might be used internally in the future if we
            decide to start expiring DirectoryItem's internally while a process runs.
            Right now, all DirectoryItem's stay valid the entire length of a process's life-cycle.

            If you pass in an int, it will be converted into a datetime via `utcfromtimestamp()`;
            this is how it's stored in dynamo.

        cacheable:
            This is not included or retrieved from JSON. This is sort of a flag to indicate
            the DynamoCacher [or some other cacher] should not cache this item, as it's specific
            to the current instance/process.  This is normally only set to False if a DirectoryItem
            is provided from the EnvironmentalProvider [ie: an environmental variable].

        .. todo:: Document other args, for now see individual class variable docs below.
    """
    # Must have some sort of 'value' on the class for pdoc3 to pick up vars.

    directory: Optional[Union[Directory, str]] = None
    """ This will always return a non-None directory object. If you give it a str in __init__,
        converts it to a Directory object for you.
    """

    name: str = None
    """ This will always return a non-None name string, in lower-case.
        Whatever string is passed into this while creating a DirectoryItem object,
        DirectoryItem will lower-case it.

        You can see the name orginally used for this value by getting
        `DirectoryItem.original_name`.
    """

    value: DirectoryItemValue = None
    """ Value  """

    original_name: str = None
    """ The original name of the value, before case was changed.
        If this is not set to anything when `DirectoryItem` is created,
        it will be set to `self.name`, before DirectoryItem lower-cases `self.name`.
    """

    source: str = None

    ttl: Union[dt.datetime, int] = None
    """ If give me an `int`, I'll convert it to a datetime for you;
        reading this var will always give you a `None` or a `datetime`.
    """

    cacheable: bool = True

    created_at: Optional[dt.datetime] = field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )
    """ Set at object creation by default to current date/time, you can pass in your own if needed.
        This happens when the item comes from Dynamo [ie: we store creation date in dynamo].
        If the item in Dynamo has no creation date, this will be None; this indicates an unknown
        creation date.
    """

    # These are only used by the dynamo cache table.
    cache_range_key: str = None
    """ If set, this is used for 'name' in the dynamo table. The range key contents was changed
        for the cache table. I left it as 'name' so I could have it backwards compatible with
        older/existing config objects.

        So if `cache_dynamo_range_key` exists, we will map it to 'dynamo-table.name',
        and `DirectoryItem.name` will be mapped to 'dynamo-table.real_name'.
        Otherwise, `DirectoryItem.name` is mapped to `dynamo-table.name`.

        This will be set for you if you provide only a `cache_concat_directory_paths`
        and `cache_concat_provider_names`. We will put them together with a `+` between them.

        At some point we may create a global-all-configCacheV2 table and have better names on it.
    """
    cache_concat_directory_paths: str = None
    cache_concat_provider_names: str = None

    cache_hash_key: str = None
    """ This is used for the `directory` in the Dynamo table. The hash-key contents were changed
        for the cache dynamo table. I left it as `directory` on the table so it can be backwards
        compatible with the older Config class.

        This is mapped to dynamo-table.directory, and `DirectoryItem.directory` will be mapped
        to `dynamo-table.real_directory`.

        At some point we may create a global-all-configCacheV2 table and have better names on it.
    """

    from_cacher: bool = False
    """ If True, this item came from the dynamo cache table (or a cacher in general).
        If False (default): Came from original source.
    """

    @property
    def supplemental_metadata(self) -> JsonDict:
        return self._supplemental_info  # noqa: This exists (see __post_init__)

    def add_supplemental_metadata(self, name: str, value):
        self._supplemental_info[name] = value   # noqa: This exists (see __post_init__)

    # todo:
    #  Now that we split the libraries, we should import and use `xyn-model.JsonModel`:
    #  Literally all of the code in json() and __init__() and __repr__ and get some extra features
    #  [like change tracking, etc].
    def __post_init__(self):
        directory = self.directory
        if directory is None:
            object.__setattr__(self, 'directory', Directory.from_non_existent())
        elif isinstance(directory, str):
            object.__setattr__(self, 'directory', Directory.from_path(directory))

        if not self.original_name:
            object.__setattr__(self, 'original_name', self.name)

        # todo: May want to have a cached mapping of Names to standard-format [optimization].
        object.__setattr__(self, 'name', self.name.lower())

        # Use class default values if possible.
        ttl = self.ttl
        if ttl is not None and isinstance(ttl, int):
            ttl = dt.datetime.fromtimestamp(ttl, dt.timezone.utc)
            object.__setattr__(self, 'ttl', ttl)

        # ensure it's a bool
        object.__setattr__(self, 'cacheable', bool(self.cacheable))

        # This won't effect dataclasses eq/hash/etc, just some supplemental metadata.
        # This should NEVER effect this objects core-identity.
        object.__setattr__(self, '_supplemental_info', {})

        if (
            not self.cache_range_key and
            self.cache_concat_directory_paths and
            self.cache_concat_provider_names
        ):
            # Just need a consistent unique key for dynamo, I don't need to parse it later.
            cache_range_key = (
                f"{self.name}|+|{self.cache_concat_directory_paths}|+|"
                f"{self.cache_concat_provider_names}"
            )
            object.__setattr__(self, 'cache_range_key', cache_range_key)

    def __str__(self):
        """
        Returns a string-representation of self, it will exclude the item value
        (`DirectoryItem.value`). This is appropriate for logging purposes.

        If you print this via a debugger console, it will include the value by default.
        """
        return self.__repr__(include_value=False)

    def __repr__(self, include_value=True, include_length=False):
        """ Returns a string representation of the item.
            Args:
                include_value: If True (default), will include the value in the returned string.
                    If False: value is excluded.

                    .. important:: This will be `False` if you convert this item to a string
                        via `DirectoryItem.__str__`.  If you print this object on debugger
                        console, it will include the value.
        """
        # todo: Someday if I could use the sdk here.... I could eliminate most or all of this code.
        desc = f"DirectoryItem(name='{self.name}', directory='{self.directory.path}'"

        value = self.value
        if include_value:
            desc += f", value='{value}'"

        if self.source:
            desc += f", source='{self.source}'"

        if self.ttl:
            desc += f", ttl='{self.ttl}'"

        desc += ')'
        return desc

    @classmethod
    def from_json(cls, json: JsonDict, append_source: str = '', from_cacher: bool = False):
        """
        Args:
            json: Dict from previous call to `json()` in the past.
                Recreates the same directory item.
            append_source: If provided, will append to 'source' in json the string.
                If json has no 'source' string, append_source will set into self.source.
            from_cacher: If True, this item came from the dynamo cache table
                (or a cacher in general).
                If False (default): Came from original source.
        """
        # todo: Someday if I could use the sdk here.... I could eliminate most or all of this code.
        real_name = json.get('real_name')
        cache_range_key = None

        if real_name:
            name = real_name
            cache_range_key = json['name_key']
        else:
            name = json['name']

        # If `original_name` is None, then __post_init__ will use `self.name` for it for us.
        original_name = json.get('original_name')
        real_directory = json.get('real_directory')
        cache_hash_key = None

        if real_directory:
            directory = real_directory
            cache_hash_key = json['app_key']
        else:
            directory = json['directory']

        directory = Directory.from_path(directory)
        if not cache_hash_key:
            cache_hash_key = directory.path

        value = json.get('value', None)
        ttl = json.get('ttl', None)
        ttl = int(ttl) if ttl else None
        source = json.get('source', None)
        if append_source:
            if source is None:
                source = append_source
            else:
                source += append_source

        cache_concat_directory_paths = json.get('cache_concat_directory_paths')
        cache_concat_provider_names = json.get('cache_concat_provider_names')

        created_at = json.get('created_at', None)
        created_at = ciso8601.parse_datetime(created_at) if created_at else None

        return DirectoryItem(
            directory=directory,
            cache_range_key=cache_range_key,
            cache_hash_key=cache_hash_key,
            name=name,
            original_name=original_name,
            value=value,
            source=source,
            ttl=ttl,
            created_at=created_at,
            cache_concat_directory_paths=cache_concat_directory_paths,
            cache_concat_provider_names=cache_concat_provider_names,
            from_cacher=from_cacher
        )

    def json(self, include_value=True) -> JsonDict:
        """ Provides a dict that can easily be serialized into JSON.
            The JSON provided is able to be directly put into a Dynamo Table if desired.
        """
        # todo: Someday if I could use the sdk here.... I could eliminate most or all of this code.

        cache_range_key = self.cache_range_key
        cache_hash_key = self.cache_hash_key

        if not cache_range_key or not cache_hash_key:
            raise ConfigError(
                f"need to have cache_hash_key ({cache_hash_key}) and "
                f"cache_range_key ({cache_range_key}) set to create JSON from DirectoryItem"
                f"{self}."
            )

        # See the doc-comments for `DirectoryItem.cache_hash_key` for more details of
        # why we are mapping `directory/name` to `real_(name/directory)`.
        response = {
            'name_key': cache_range_key,
            'app_key': cache_hash_key,
            'real_name': self.name,
            'original_name': self.original_name,
            'real_directory': self.directory.path,
            'cache_concat_provider_names': self.cache_concat_provider_names,
            'cache_concat_directory_paths': self.cache_concat_directory_paths,
        }

        if include_value and self.value is not None:
            response['value'] = self.value

        if self.ttl:
            response['ttl'] = int(self.ttl.timestamp())

        if self.source:
            response['source'] = str(self.source)

        if self.created_at:
            response['created_at'] = self.created_at.isoformat()

        return response


class DirectoryListing:
    directory: Directory = None
    """ Metadata: used by external parties to keep track of the directory this listing belongs to.
        This is only for informational purposes, and is not used internally by the DirectoryListing
        class.

        Defaults to None.
    """

    _items: Dict[str, DirectoryItem]

    def __init__(self, directory: Directory = None, items: Iterable[DirectoryItem] = None):
        self.directory = directory
        self._items = {}
        for item in xloop(items):
            self.add_item(item)

    def get_any_item(self) -> Optional[DirectoryItem]:
        if not self._items:
            return None

        return next(iter(self._items.values()))

    def add_item(self, item: DirectoryItem):
        self._items[item.name] = item

    def remove_item_with_name(self, name: str):
        """
        Remove item with name from my directory listing.

        Args:
            name str: Name of item to remove. If item does not exist, nothing happens.

        """
        self._items.pop(name.lower(), None)

    def get_items_with_different_value(
        self, items: Iterable[DirectoryItem]
    ) -> Iterable[DirectoryItem]:
        """
        Figures out which of the items passed in are either not present or if they are have
        a different `.value`. It ignores the other properties on DirectoryItem for this comparison.

        This means if name 'A' with value '1' currently exists in self, and you pass in an item
        with name 'A' with value '1' via this method, it would not be returned since it's already
        present. However, if you pass an item with name of 'B' with value '2', it would be
        returned because the value is different.

        Keep in mind I return a generator, so if you make changes while I iterate, it will use
        that new value for comparisons past that point. You can modify self while using the
        returned generator, but you should not modify passed in `items` while using generator.

        :param items: Items to look at see if they are already present or not.
        :return: A generator for `items` where it's `.value` is different from what I already have.
        """
        map = self._items
        for item in items:
            my_item = map.get(item.name)
            if not my_item or my_item.value != item.value:
                yield item

    def get_item(self, name: str) -> Optional[DirectoryItem]:
        """ Gets a item in a case-insensitive way, returns None if item does not exist in self. """
        return self._items.get(name.lower(), None)

    def item_mapping(self) -> Mapping[str, DirectoryItem]:
        """ Read-only mapping of the items name to the item [reminder: names are in lower-case].
        """
        return MappingProxyType(self._items)


# noinspection PyTypeChecker
_path_to_directory_cache: Dict[str, Directory] = weakref.WeakValueDictionary()
