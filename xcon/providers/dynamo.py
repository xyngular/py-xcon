from __future__ import annotations

import dataclasses
import datetime as dt
import logging
import os
import random
from collections import defaultdict
from typing import Dict, Optional, Callable, Iterable, Sequence, Tuple
from typing import Mapping

from boto3.dynamodb import conditions
from xboto.resource import dynamodb
from xsentinels import Default
from xloop import xloop

from xcon.directory import Directory, DirectoryListing, DirectoryOrPath, DirectoryItem, \
    DirectoryChain
from xcon.exceptions import ConfigError
from xcon.provider import ProviderCacher, ProviderChain, AwsProvider, \
    InternalLocalProviderCache
from .common import handle_aws_exception

log = logging.getLogger(__name__)


class DynamoProvider(AwsProvider):
    """
    Access a dynamo tabled called `global-all-config` when searching for a config value.
    This provider allows one to have a structured list or dictionary. It supports JSON
    and will parse/decode it when it gets it from Dynamo into a real Python dict/list/str/etc!
    """
    name = "dynamo"
    _directories: Dict[Directory, DirectoryListing]

    @property
    def _table(self) -> _ConfigDynamoTable:
        # todo: make table name configurable
        return _ConfigDynamoTable(table_name='global-all-config')

    def get_item(
            self,
            name: str,
            directory: Optional[DirectoryOrPath],
            directory_chain: DirectoryChain,
            provider_chain: ProviderChain,
            environ: Directory
    ) -> Optional[DirectoryItem]:
        if directory is None:
            return None

        directory = Directory.from_path(directory)
        listing = self.local_cache.get(directory)
        if listing:
            return listing.get_item(name)

        # We need to look up the directory listing from Dynamo.
        items = []

        try:
            if self.botocore_error_ignored_exception:
                # Raise same error we previously had, and handle it the same way
                # for this new directory.
                log.info(
                    f"We've already previously had a botocore error. Botocore error's [vs client"
                    f"errors] are generally related to something that will keep failing. "
                    f"Assuming we can't do anything with the service so bailing out early via "
                    f"the same previous exception; for directory {directory}."
                )
                raise self.botocore_error_ignored_exception from None

            items = list(self._table.get_items_for_directory(directory=directory))
            self.log_about_items(items=items, path=directory.path)
        except Exception as e:
            # Will either re-raise the exception or handle it for us.
            handle_aws_exception(exception=e, provider=self, directory=directory)

        listing = DirectoryListing(directory=directory, items=items)
        self.local_cache[directory] = listing
        return listing.get_item(name)

    def retrieved_items_map(
            self, directory: DirectoryOrPath
    ) -> Optional[Mapping[str, DirectoryItem]]:
        directory = Directory.from_path(directory)
        listing = self.local_cache.get(directory)
        if listing is None:
            return None
        return listing.item_mapping()


class DynamoCacher(ProviderCacher):
    """ Uses a Dynamo table called `global-all-configCache`.

        Generally caches what configuration values we lookup into a dynamo table.
        A good summary would be in the [Config Overview - Caching](../config.html#caching)

        More details about the table struvture its self follows.

        The table has two keys:

        1. Hash key: Is the `environ` method parameter that gets passed to the methods on me.
           It's normally a string in this format: `/{APP_NAME}/{APP_ENV}`.
           Also, normally apps/services are only given access to one specific hash-key.
           This hash-key should represent the app and its current environment.
        2. Range/Sort key: Contains the variable name, providers and directory paths used
           to lookup value. This makes it so the app can do various queries using various
           different providers/directories and the cacher can cache those results correctly
           and uniquely based on the var-name, providers and directories originally
           used to get the value.

        You don't need to parse the rage/sort-key.
        All of its components are also separate attributes in the table on the row.

        ## Dependency Details

        Right now the `DynamoCacher` is a `xinject.dependency.Dependency`
        resource, you can grab the current one by calling `DynamoCacher.grab()`.

        More specifically: we are a `xinject.dependency.Dependency`, which means that there is
        normally only one of us around. See xinject library for more details.
    """
    name = "cacher"
    _ttl: dt.datetime

    def retrieved_items_map(self, directory: DirectoryOrPath) -> Mapping[str, DirectoryItem]:
        """ This is mostly useful for getting this to cache, so I am not going to implement it
            in the cacher (if we ever do, the `xcon.provider.ProviderChain` will have to
            figure out how to skip us).

        """
        return {}

    @property
    def _table(self) -> _ConfigDynamoTable:
        # todo: make table name configurable
        table = _ConfigDynamoTable(table_name='global-all-configCache', cache_table=True)
        table.append_source = " - via cacher"
        return table

    @dataclasses.dataclass
    class _LocalCache:
        listings: Dict[Directory, Dict[str, Dict[str, DirectoryListing]]] = dataclasses.field(
            default_factory=(
                lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(DirectoryListing)))
            )
        )
        environ_to_items: Dict[Directory, Tuple[DirectoryItem]] = dataclasses.field(
            default_factory=lambda: {}
        )

    @property
    def local_cache(self) -> _LocalCache:
        # Using default dict, so I don't have to worry about allocating the dict's my self later.
        maker = lambda c: DynamoCacher._LocalCache()
        cacher = InternalLocalProviderCache.grab()
        return cacher.get_cache_for_provider(provider=self, cache_constructor=maker)

    def __init__(self):
        """
        ## How to Clear Cache

        If you need to change the config and have it propagate asap, you can easily
        just delete all items in the dynamo cache table for cache_key for the service/env.

        So for now, I am giving a long-life to the cached-items, since config changes to
        existing items are rare [if we need a new item and it's not in cache it will be looked
        up immediately and then cached].

        I use a random number to try to help ensure we try not to have synchronous times on when
        various things expire between various different services, to help spread load between
        param store and secrets manager aws api's.

        12 hours in the future with a random +/- 1500 seconds added on is what we currently do.
        Thinking about making it a shorter period of time [a couple of hours].
        """
        self._table.append_source = " - via cacher"

        super().__init__()
        self._ttl = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
            hours=12, seconds=random.randint(-1500, 1500)
        )

    def cache_items(
            self,
            items: Iterable[DirectoryItem],
            provider_chain: ProviderChain,
            directory_chain: DirectoryChain,
            environ: Directory
    ):
        """ Cache's passed in item, using the other params to create the proper range and hash
            keys that we use in Dynamo to uniquely identify the item.

            See `DynamoCacher.get_item` for more details on what the Args mean. It uses many of
            the same ones.

            For and overview of the caching process, see
            [Config Overview - Caching](../config.html#caching)

        """
        environ = self._get_environ_to_use(environ)
        listing = self._get_listing(
            directory_chain=directory_chain,
            provider_chain=provider_chain,
            environ=environ
        )
        items_to_send = []
        for new_item in listing.get_items_with_different_value(items):
            if new_item.cacheable:
                ttl = self._ttl
                # If the item has a ttl, we want to use that. It means it's a temporary value
                # that should be looked up again after the expiration date.
                if new_item.ttl:
                    # We should never get a ttl less then the current time; but if we do we will
                    # insert an item into cacher that will never be read by other processes
                    # [since the cacher will filter them out via a dynamo query-filter].
                    ttl = new_item.ttl

                concat_dir_paths = directory_chain.concatenated_directory_paths
                concat_provider_names = provider_chain.concatenated_provider_names

                item_to_cache = DirectoryItem(
                    directory=new_item.directory,
                    name=new_item.name,
                    value=new_item.value,
                    source=f"{new_item.source} - {new_item.directory.path}",
                    ttl=ttl,
                    # DirectoryItem will calculate a cache_range_key for us with these two values:
                    cache_concat_directory_paths=concat_dir_paths,
                    cache_concat_provider_names=concat_provider_names,
                    cache_hash_key=environ.path,
                )
                items_to_send.append(item_to_cache)
                listing.add_item(item_to_cache)

        if not items_to_send:
            return

        self.log_about_items(
            items=items_to_send,
            path=environ.path,
            msg_prefix="Sending to cache"
        )

        if self.directory_has_error(environ):
            log.debug(
                f"Not saving cached items to {environ}, it had an error reading/writing "
                f"previously. See previous log messages [whenever the error happened for first "
                f"time] for more details."
            )
            return

        try:
            self._table.put_items(items_to_send)
        except Exception as e:
            # Will either re-raise the exception or handle it for us.
            # It will also communicate to us via marking the directory as error'd on us if needed.
            handle_aws_exception(exception=e, provider=self, directory=environ)

    def get_item(
            self,
            name: str,
            directory: Optional[DirectoryOrPath],
            directory_chain: DirectoryChain,
            provider_chain: ProviderChain,
            environ: Optional[Directory]
    ) -> Optional[DirectoryItem]:
        """
        Returns item out of the cache. Cache-key is constructed using directory_chain,
        provider_chain, environ and name.

        For and overview of the caching process, see
        [Config Overview - Caching](../config.html#caching)

        Args:
            name: Name of the config value, ie: `XYNAPI_BASE_URL`.
            directory: Directory to lookup value in, this is not really used right now by
                cacher. But it's used by the other providers. This cacher acts just like
                a provider and so accepts the parameter.
            directory_chain: Current directory chain that is being used to lookup value.
                Used as part of the rang-key in the Dynamo table.
            provider_chain (xcon.provider.ProviderChain): Current provider chain
                that is being used to lookup value. Used as part of the rang-key in the Dynamo
                table.
            environ:
                This is the directory the cacher uses for the hash-key. It's supposed to have
                the full service and environment name.

                Example Directory Path: `/hubspot/testing`

        Returns:
            xcon.directory.DirectoryItem: If we have a cached item, this is it.
            None: Otherwise we return None indicating nothing has been cached.
        """
        # Cache needs all of this stuff to do proper caching.
        environ = self._get_environ_to_use(environ)
        if not directory or not directory_chain or not environ:
            return None

        return self._get_listing(
            directory_chain=directory_chain,
            provider_chain=provider_chain,
            environ=environ,
        ).get_item(name)

    def _get_listing(
            self,
            directory_chain: DirectoryChain,
            provider_chain: ProviderChain,
            environ: Directory
    ) -> DirectoryListing:
        dir_paths = directory_chain.concatenated_directory_paths
        provider_names = provider_chain.concatenated_provider_names

        # defaultdict will provide default versions of all the objects as-needed.
        listing = self.local_cache.listings[environ][dir_paths][provider_names]

        # If we have a directory assigned to object [defaults to None], then we know we
        # have retrieved it in the past at some point, return it.
        if listing.directory is not None:
            return listing

        listing.directory = environ
        items = self._get_items_for_environ(environ=environ)
        concat_directory_paths = directory_chain.concatenated_directory_paths
        concat_provider_names = provider_chain.concatenated_provider_names
        for item in items:
            # find all items in the environ items that match my directory/provider lists.
            # IF they do match, then it's safe to use the cached value.
            if item.cache_concat_directory_paths != concat_directory_paths:
                continue
            if item.cache_concat_provider_names != concat_provider_names:
                continue
            listing.add_item(item)
        return listing

    def _get_items_for_environ(self, environ: Directory) -> Iterable[DirectoryItem]:
        items = self.local_cache.environ_to_items.get(environ)
        if items is not None:
            return items

        now = dt.datetime.now(dt.timezone.utc)
        expire_time = now + dt.timedelta(seconds=random.randint(0, 60 * 60 * 2))
        try:
            items = self._table.get_items_for_directory(directory=environ, expire_time=expire_time)

            # Ensure we have a list, and not a generator.
            items = tuple(xloop(items))

            # Log about stuff we retrieved from the cache table.
            self.log_about_items(items=items, path=environ.path)
        except Exception as e:
            # Will either re-raise the exception or handle it for us.
            handle_aws_exception(exception=e, directory=environ, provider=self)
            items = tuple()

        self.local_cache.environ_to_items[environ] = items
        if not items:
            return items

        # ttl per-environ?
        item_ttl = items[0]
        if not item_ttl:
            return items

        # We want to try and have the cache expire at around the same time if possible;
        # check item for it's ttl and use that.
        item_ttl = item_ttl.ttl
        current_ttl = self._ttl
        future_limit = current_ttl + dt.timedelta(days=2)
        now_limit = current_ttl + dt.timedelta(minutes=1)
        if item_ttl and now_limit <= item_ttl <= future_limit:
            self._ttl = item_ttl

        return items

    def _get_environ_to_use(
        self, passed_in_environ: Optional[Directory] = None
    ) -> Optional[Directory]:
        """
        Looks at environmental vars SERVICE_NAME and APP_ENV,
        if they both exist and are not blank we will use that and return those
        values inside an environ Directory object.

        Otherwise, we will return the passed_in_environ, which should be the one
        that came from Config and is based on that Config's Config.APP_ENV and Config.SERVICE_NAME.
        """
        from xcon import xcon_settings
        e_service = xcon_settings.service
        e_env = xcon_settings.environment

        if not e_service or not e_env:
            return passed_in_environ

        return Directory(service=e_service, env=e_env)


# Most of this code could be shared from `xyn_model_dynamo`, but we don't want to import that
# in this library (it's a bit heavy).  So for now, we are duplicating some of that functionality
# for use here, in a much simpler (but WAY less feature-rich) way:
class _ConfigDynamoTable:
    """
    Meant to be a simple abstract around dynamo table, just enough for our needs in this
    `dynamo.py` module file...

    After doing all the needed work for getting/updating items and so forth,
    you should throw-away the `_ConfigDynamoTable` object and lazily create a new one next time a
    call from the user comes in that needs the table.

    This helps support dependency injection of the dynamodb boto3 resource via xinject
    (always uses dependency when called, so it can be changed/injected by user).
    """
    append_source = "dynamo"

    @property
    def table_name(self) -> str:
        """ DynamoDB table name. """
        return self._table_name

    @property
    def table(self):
        """ DynamoDB table resource.
            We lazily get the resource, so we don't have to verify/create it if not needed.
        """
        table = self._table
        if table is not None:
            return table

        table = dynamodb.Table(self.table_name)
        self._table = table
        return table

    def __init__(
            self,
            table_name: str,
            cache_table: bool = False
    ):
        super().__init__()
        self._table_name = table_name
        self._table = None
        self._verified_table_status = False
        self._cache_table = cache_table

    def put_item(self, item: DirectoryItem):
        """ Put item into dynamo-table.

            :param item:
                Item to put in.
        """

        resource = self._batch_writer
        if not resource:
            resource = self.table

        resource.put_item(Item=item.json())

    def put_items(self, items: Sequence[DirectoryItem]):
        """ Uses a batch-writer to put the items.
            WAY more efficient than doing it one at a time.
            If you only give me one item, directly calls `put_item` without a batch-writer.
        """
        if not items:
            return

        if len(items) == 1:
            self.put_item(item=items[0])
            return

        with self._with_batch_writer():
            for i in items:
                self.put_item(item=i)

    def delete_items(self, items: Iterable[DirectoryItem]):
        # This is really only used with unit-tests, I am not going to try to batch-delete
        # the items. Just doing to do it the slower/simpler way of one at a time.
        # If we really need to make this faster for some reason look at how
        # xyn-model-dynamo batch-deletes items.
        table = self.table
        for i in items:
            table.delete_item(Key={
                'app_key': i.cache_hash_key,
                'name_key': i.cache_range_key
            })

    def get_items_for_directory(
            self, directory: DirectoryOrPath, expire_time: dt.datetime = Default
    ) -> Iterable[DirectoryItem]:
        """
        Gets all items for a particular directory.
        :param directory:
        :param expire_time:
            Date to use to filter expired items by.
            if Default:
                By Default we calculate the current date/time and use that.
            if None:
                All items regardless of their expiration time will be returned.  Keep in mind
                that DynamoDB only guarantees an expired item will be deleted within 48 hours,
                so it will only be returned if DynamoDB has not deleted the item yet.
            If dt.datetime:
                I'll use the provided datetime for the expiry time. Items will only be returned
                if they don't have an expiration time, or if their expiration time is greater
                than the provided date/time.

        :return:
        """
        dir_path = Directory.from_path(directory).path
        expression = conditions.Key('app_key').eq(dir_path)

        log.info(f"Getting Dynamo directory ({directory.path}).")

        if expire_time is Default:
            expire_time = dt.datetime.now(dt.timezone.utc)

        filter_exp = None
        if expire_time is not None:
            ttl_attr = conditions.Attr('ttl')
            filter_exp = ttl_attr.not_exists() | ttl_attr.gt(int(expire_time.timestamp()))

        def response_creator(last_key: str):
            query = {
                # I think we are fine without a `ConsistentRead`, we rarely write/put things,
                # And if it was out-of-date it would only be by a matter of seconds which really
                # does not matter to us in this context.
                #
                # "ConsistentRead": True,

                # Expression for the directory-partition we want.
                "KeyConditionExpression": expression,
            }

            if filter_exp:
                query["FilterExpression"] = filter_exp

            if last_key:
                query["ExclusiveStartKey"] = last_key

            return self.table.query(**query)

        return self._paginate_all_items_generator(response_creator)

    def get_all_items(self) -> Iterable[DirectoryItem]:
        def response_creator(last_key: str):
            if last_key is None:
                return self.table.scan()
            return self.table.scan(ExclusiveStartKey=last_key)

        return self._paginate_all_items_generator(response_creator)

    def _with_batch_writer(self):
        """ Uses a batch-writer to put the items.
            WAY more efficient than doing it one at a time.

            You can use a batch writer via a `with` and then create another batch writer
            via `with_batch_writer()` and enter that one via `with` while the first one is
            active without a problem. You MUST not use a `with` a second time with the same
            batch-writer object [ie: with one one call to `with_batch_writer()`].

            You need to use this in a `with` statement, like so:
            ```
            table = HubspotContactSyncTable()
            with table.with_batch_writer():
                for item in items:
                    table.put_item(item)
            ```

            Or you can use `put_items` and just give it a list of items, and it will do
            this for you (create and use a batch writer).
        """
        return self._BatchTable(self)

    # ----------------------------
    # --------- Private ----------

    _table_name: str
    _verified_table_status: bool
    _batch_writer = None

    def _paginate_all_items_generator(
            self, response_creator: Callable[[Optional[str]], dict]
    ) -> Iterable[DirectoryItem]:
        last_key: Optional[str] = None
        append_source = self.append_source

        while True:
            response = response_creator(last_key)
            last_key = response.get('LastEvaluatedKey', None)

            db_datas = response['Items']
            if not db_datas:
                db_datas = []

            for data in db_datas:
                yield DirectoryItem.from_json(
                    json=data,
                    append_source=append_source,
                    from_cacher=self._cache_table
                )

            if not last_key:
                return

    class _BatchTable(object):
        """
        Used by ``Table`` as the context manager for batch writes.

        You likely don't want to try to use this object directly.
        """
        table: _ConfigDynamoTable
        _batch_writer = None

        def __init__(self, table):
            self.table = table

        def __enter__(self):
            if self._batch_writer is not None:
                raise ConfigError(
                    "Must not use `with` multiple times with same dynamo batch writer object."
                )

            if self.table._batch_writer:
                # Nothing to do if table already has a batch-writer.
                return

            batch_writer = self.table._create_batch_writer()
            batch_writer.__enter__()
            self.table._batch_writer = batch_writer
            self._batch_writer = batch_writer
            return self

        def __exit__(self, type, value, traceback):
            if not self._batch_writer:
                return

            # Only remove batch-writer if we were the one who set it originally.
            self.table._batch_writer = None
            self._batch_writer.__exit__(type, value, traceback)

    def _create_batch_writer(self):
        return self.table.batch_writer(overwrite_by_pkeys=['app_key', 'name_key'])
