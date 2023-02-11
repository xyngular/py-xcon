from __future__ import annotations

import os
from typing import Optional, Mapping, Dict, Any

from xcon.directory import (
    DirectoryOrPath, DirectoryItem, DirectoryChain, Directory, DirectoryListing
)
from xcon.provider import Provider, ProviderChain, InternalLocalProviderCache


class EnvironmentalProvider(Provider):
    """
    Provides config values out of the current processes environmental variables.
    Pretty strait-forward. Normally this is the first provider in the provider-chain.
    """
    query_before_cache_if_possible = True
    needs_directory = False
    name = "env"

    _log_msg_prefix = '?'
    """
    `EnvironmentalProvider` lazily makes a snapshot of all current environmental variables
    at the time that we first need to look up a value. All keys are lower-cased.

    It's possible to pass in a set of values via `__init__` method if you have an alternate
    way you want to get/provide the environmental variables, ie:

    >>> my_own_env_provider = EnvironmentalProvider({'some_env_var': 'some-value'})
    >>> def will_use_custom_env_provider
    >>>     with my_own_env_provider:
    ...         assert config.SOME_ENV_VAR == 'some-value'
    """

    _user_provided_cache: DirectoryListing = None
    """ If user provided the 'cache' of names/values, we store it here so it's permanent
        and won't expire like the normal env-var cache will.

        Always call `self.local_cache`, it will do the right thing and return you what you need,
        a fully-filled out snapshot either from user or from local env-vars.
    """

    @property
    def local_cache(self) -> DirectoryListing:
        # Using default dict so I don't have to worry about allocating the dict's my self later.
        if self._user_provided_cache is not None:
            return self._user_provided_cache

        maker = lambda c: self._create_snapshot(None, c)
        cacher = InternalLocalProviderCache.grab()
        return cacher.get_cache_for_provider(provider=self, cache_constructor=maker)

    def __init__(self, env_vars: Optional[Dict[str, Any]] = None):
        """ By default we will snapshot `os.environ` the first time I am asked for a value/item.
            You can override what values I will return if you pass in a value for `env_vars`.

            Should be a dict of environmental variable names to string values.
         """
        super().__init__()
        # If we don't get passed in anything, we will lazily get them from `os.environ`.
        if env_vars is not None:
            # We got passed in the explicit values.
            self._create_snapshot(env_vars)

    def _create_snapshot(
        self,
        from_env_dict: Dict[str, Any] = None,
        internal_cache_provider: InternalLocalProviderCache = None
    ):
        """
        Make a snapshot of current environment, lower-casing all variables.
        Stores in `EnvironmentalProvider._env_vars_snapshot`.

        If you pass in a dict, we will use that to make the snapshot instead.

        .. info:: The other providers use lower-case names for everything, we will likely
           get queried with lower-case names, so doing in here not only normalizes the
           case of the env-keys and simplified it, but also makes it a bit more efficient.

        Args:
            from_env_dict: User provided set of permanent name/values to use for our cache.

                If you pass None (default): we will use `os.environ` instead and cache this in
                an InternalLocalProviderCache

            internal_cache_provider: If provided, we will use this as the object to store
                our environmental snapshot on.
                If not provided, we will get the `InternalLocalProviderCache.grab()`
                (current instance).

                In either case, we won't use a `InternalLocalProviderCache` if you pass
                in a non-None value for `from_env_dict` as that's permanent.
        """

        # IMPORTANT: DO NOT use `self.local_cache` in this method,
        #            self.local_cache can call me to create cached snapshot!

        listing = DirectoryListing()

        if from_env_dict is None:
            # If an internal cacher not provided, get current one.
            if not internal_cache_provider:
                internal_cache_provider = InternalLocalProviderCache.grab()

            from_env_dict = os.environ
            msg_prefix = "Snapshotted os.environ"
            internal_cache_provider.set_cache_for_provider(
                provider=self, cache=listing
            )
        else:
            msg_prefix = "Given (User Provided)"
            self._user_provided_cache = listing

        for k, v in from_env_dict.items():
            item = DirectoryItem(
                directory="/_environmental", name=k, value=v, cacheable=False,
                source=self.name
            )
            listing.add_item(item)

        self._log_msg_prefix = msg_prefix
        self._log_about_environmental_snapshot()

    def _log_about_environmental_snapshot(self):
        """ Will log out the names of what environmental variables I snapshot,
            if the snapshot exists (it's normally lazily Snapshotted first time it's needed).
        """
        self.log_about_items(
            items=self.local_cache.item_mapping().values(),
            path='/_environmental',
            msg_prefix=self._log_msg_prefix
        )

    def get_item_without_environ(self, name: str) -> Optional[DirectoryItem]:
        """
        We really don't need all the passed in info, since we don't deal with paths
        in the environmental provider [just names only]. So here is an easy way to
        run the same logic that we normally do but without needing to pass in the
        directory_chain, provider_chain, etc like you do in the normal
        method we usually use: `EnvironmentalProvider.get_item`.

        Args:
            name (str): We upper case this string for you and look in `os.getenv()` for the value.
        """
        # Snapshot cache uses lower-case keys, see `EnvironmentalProvider._create_snapshot`.
        return self.local_cache.get_item(name)

    def get_value_without_environ(self, name: str) -> Optional[str]:
        """
        We really don't need all the passed in info, since we don't deal with paths
        in the environmental provider [just names only]. So here is an easy way to
        run the same logic that we normally do but without needing to pass in the
        directory_chain, provider_chain, etc like you do in the normal
        method we usually use: `EnvironmentalProvider.get_item`.

        Args:
            name (str): We upper case this string for you and look in `os.getenv()` for the value.
        """
        # Consider looking for any case, for now only look for upper-case names.
        item = self.get_item_without_environ(name=name)
        if item is None:
            return None

        return item.value

    def get_item(
            self,
            name: str,
            directory: Optional[DirectoryOrPath],
            directory_chain: DirectoryChain,
            provider_chain: ProviderChain,
            environ: Directory
    ) -> Optional[DirectoryItem]:
        # We really don't need all the passed in info, since we don't deal with paths
        # in the environmental provider [just names only].
        return self.get_item_without_environ(name=name)

    def retrieved_items_map(
            self, directory: DirectoryOrPath
    ) -> Mapping[str, DirectoryItem]:
        """ We don't keep track of these [we retrieve them each time from os.getenv].
            We could also just grab all the environmental vars and return them, but I just don't
            think it's that useful for us in this provider, for now just always return
            an empty map.

            We also don't want to cache anything from the environmental provider into the Dynamo
            cache anyway, so another reason to return an empty dict.

            We don't want to return None, the ProviderChain uses {} vs None to decide if it should
            stop looking for more `retrieved_items_map` as a safety mechanism.
        """
        return {}
