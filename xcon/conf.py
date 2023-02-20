from xsettings import Settings as _Settings, SettingsField
from typing import Type, Optional, Sequence
from .directory import DirectoryListing, Directory
from . import providers
from .provider import Provider
from xsettings.env_settings import EnvVarRetriever


_env_retriever = EnvVarRetriever()


class XconSettings(_Settings):
    def __init__(self):
        super().__init__()
        # TODO: Find a simpler/easier way to allocate mutable things like `dict`m `list`,
        #  empty-objs and so on; on a per-instance basis.
        self.defaults = DirectoryListing()

    service: str = SettingsField(
        name='APP_NAME', retriever=_env_retriever, default_value='global'
    )
    """ Defaults to `APP_NAME` environment variable; otherwise will fallback to using 'global'. """

    environment: str = SettingsField(
        name='APP_ENV', retriever=_env_retriever, default_value='all'
    )
    """ Defaults to `APP_ENV` environment variable; otherwise will fallback to using 'all'. """

    defaults: DirectoryListing
    """
    A blank DirectoryListing is created per-instance for this setting,
    feel free to directly modify it to add/remove whatever default config values you want
    for the overall defaults (ie: used by all config instances as the last place to check
    before giving up on finding a value for a particular config value.

    `xcon.config.Config` will always check it's self first for any defaults that are set
    on a particular field before doing a final fall-back to check this overall defaults
    setting for a value.
    """

    directories: Sequence[Directory] = (
        Directory('/{service}/{environment}'),
        Directory('/{service}/all'),
        Directory('/global/{environment}'),
        Directory('/global/all'),
    )
    """
    Default list of directories to use.

    By default `{service}` will be replaced with `XconSettings.service`,
    (which by default will use `APP_NAME` environmental variable).

    By default `{environment}` will be replaced with `XconSettings.environment`,
    (which by default will use `APP_ENV` environmental variable).
    """

    # XCON_INTERNAL_CACHE_EXPIRATION_MINUTES
    internal_cache_expiration_minutes: int = SettingsField(
        name='XCON_INTERNAL_CACHE_EXPIRATION_MINUTES',
        retriever=_env_retriever,
        default_value=False
    )
    """
    Number of minutes to cache any values looked up and ached internally inside the providers.
    After the expiration is reached, and if value is needed again will lookup info lazily on
    demand.

    Keep in mind that if the dynamo cache is enabled and working that the dynamo cache table might
    still have the value.
    If it's still cached in the dynamo table then when the internal cache expires, will first look
    at dynamo cache table for value (which is MUCH faster then querying each provider).
    """

    # todo: rename without provider or somehow indicate cacher is not used too?
    only_env_provider: bool = SettingsField(
        name='XCON_ONLY_ENV_PROVIDER',
        retriever=_env_retriever,
        default_value=False
    )
    """
    If `False` (default): The providers are looked up like normal.

    If `True`: No matter how the providers are configured, it will only check environmental
    variables for config values; ie: the only provider used is
    `xcon.providers.environmental.EnvironmentalProvider`.

    This is meant as more of a developer setting, for when a developer wants to ensure
    that while they run things locally it only checks environmental variables for all
    config values.
    """

    disable_default_cacher: bool = SettingsField(
        name='XCON_DISABLE_DEFAULT_CACHER', retriever=_env_retriever, default_value=False
    )
    """ Defaults to `XCON_DISABLE_DEFAULT_CACHER` environment variable
        (you can use 'True', 'T', 'False', 'F', 0, 1, 'Yes', 'Y', 'No', 'N'
         and lower-case versions of any of these)

         If environmental variable not set, Defaults to `False`.

         If `True`: By default, the cacher will be disabled (can re-enable per-Config object
         by setting it's `cacher` = `Default`.
    """

    providers: Sequence[Type[Provider]] = (
        providers.EnvironmentalProvider,
        providers.SsmParamStoreProvider,
        providers.SecretsManagerProvider
    )


xcon_settings = XconSettings.proxy()
