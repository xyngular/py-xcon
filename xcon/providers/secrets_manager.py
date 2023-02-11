from __future__ import annotations

import dataclasses
import logging

import base64
from typing import Dict, Optional, Any, Mapping

from .common import handle_aws_exception
from ..directory import Directory, DirectoryListing, DirectoryOrPath, DirectoryItem, DirectoryChain
from botocore.exceptions import ClientError
from xcon.provider import AwsProvider, ProviderChain, InternalLocalProviderCache
from xboto import boto_clients
log = logging.getLogger(__name__)


@dataclasses.dataclass
class _LocalSecretsManagerCache:
    directories: Dict[Directory, DirectoryListing] = dataclasses.field(default_factory=lambda: {})
    available: Dict[Directory, DirectoryListing] = None
    """ Items in here have None values, but it does list the dir/name of every item available
        in the secrets manager.  So if the item is in here, you know you can grab it's value.
    """


class SecretsManagerProvider(AwsProvider):
    """ Allows you to use the AWS secrets manager. It works by using the
        `secretsmanager:ListSecrets` aws permission to list all secrets it has access to.

        This way it can discover quickly if it has a secret with a specific name or not.
        This is important because it may be asked a lot due to the way we iterate though
        all the directories/providers when finding the value for a config name.

        It then uses `secretsmanager:GetSecretValue` as needed to get a specific secret value
        when it's asked for, the first time. The secrets manager does not let us bulk-get
        the secret values.  So that's why we list them first and cache that. And then only
        query for specific secrets if we know they exist.

        ## Things Left To Do

        Keep in mind that the current implementation requires use of lower-case name-strings in the
        last part of the path when writing a value into secrets manager service.
        The directory path is case-sensitive, but the last part of the path
        after the directory needs to be all-lower case.

        We assume all keys in secrets manager will be lower-cased at the moment in the current
        implementation below.

        We could make this have like the other providers, where it's case insensitive lookup but it
        can handle any actual case used for the name.

        If we start using this, we would also probably want to write some unit-tests for
        `SecretsManagerProvider`.

        We may also want to support expiring config values from local-memory after a period
        of time or restart our long-lives ECS services regularly (this would also force them
        to reconnect to the database, and so perhaps is a simpler way to accomplish database
        password rotation anyway).

        However, since we are not currently not using `SecretsManagerProvider`, these are at
        a low-priority to do right now.
    """
    name = "secrets"

    @property
    def local_cache(self) -> _LocalSecretsManagerCache:
        # Using default dict so I don't have to worry about allocating the dict's my self later.
        maker = lambda c: _LocalSecretsManagerCache()
        cacher = InternalLocalProviderCache.grab()
        return cacher.get_cache_for_provider(provider=self, cache_constructor=maker)

    def _available_names_for_directory(self) -> Dict[Directory, DirectoryListing]:
        """ A dictionary with a mapping of directory to directory list.
            The list will initially have None as the item values. THis indicates that we
            know the secret exists in AWS but we just have not gotten the value yet.

            As you update get the values and update the items in the mapped listing,
            we will keep them as-is. We only retrieve the initial listing if it does not
            exist. Otherwise, we will keep returning the cached list and won't change and
            items/values you update in it.
        """
        if self.local_cache.available is not None:
            return self.local_cache.available

        log.info("Getting full listing of available path/names in AWS Secrets Manager.")
        dir_to_item_map = {}
        try:
            paginator = boto_clients.secretsmanager.get_paginator('list_secrets')
            response = paginator.paginate()

            for page in response:
                for secret in page['SecretList']:
                    full_path: str = secret['Name']
                    split = full_path.split('/')
                    name = split.pop()
                    dir_path = '/'.join(split)

                    if not name:
                        log.warning(
                            f"Somehow got a false-looking name after splitting full-path "
                            f"({full_path}) that was retrieived from aws secrets manager."
                        )
                        continue

                    # Create a directory item with None as the value, so that
                    # we know it exists but we have not gotten the value yet.
                    # [secrets manager only has string values, so None is good enough for this].
                    item = DirectoryItem(
                        directory=dir_path,
                        # Just being paranoid, ensure it's a string.
                        name=str(name),
                        source=f"{self.name}-nameOnly"
                    )
                    directory = item.directory
                    dir_listing = dir_to_item_map.get(directory, None)
                    if not dir_listing:
                        dir_listing = DirectoryListing(directory=directory)
                        dir_to_item_map[directory] = dir_listing

                    dir_listing.add_item(item)
        except Exception as e:
            # Will either re-raise the exception or handle it for us.
            # It will also communicate to us via marking the directory as error'd on us if needed.
            handle_aws_exception(
                exception=e, provider=self, directory=Directory(path="list_secrets")
            )

        self.local_cache.available = dir_to_item_map

        for dir_listing in dir_to_item_map.values():
            self.log_about_items(
                items=dir_listing.item_mapping().values(),
                path=dir_listing.directory.path,
                msg_prefix="Retrieved only name"
            )

        return dir_to_item_map

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
        listing = self.local_cache.directories.get(directory)
        if listing:
            item = listing.get_item(name)
            if item:
                return item if item.value is not None else None

        available = self._available_names_for_directory()
        available_listing = available.get(directory)
        if not available_listing:
            return None

        # See if the item is available in the secrets manager.
        # Consider caching the available names in secret manager in Dynamo or some such.
        item = available_listing.get_item(name)
        if not item:
            return None

        # Use original_name to grab the value from aws (to preserve original case of name).
        item_path = f'{item.directory.path}/{item.original_name or item.name}'
        secret = None
        try:
            log.info(f"Getting value at SecretsManagerProvider path ({item_path})")
            item_value: Dict[str, Any] = boto_clients.secretsmanager.get_secret_value(
                SecretId=item_path
            )
            secret = item_value.get('SecretString')
            if secret is None:
                binary_data = item_value.get('SecretBinary')
                if binary_data is not None:
                    secret = base64.b64decode(binary_data)

        except ClientError as e:
            if not (e.response['Error']['Code'] == 'ResourceNotFoundException'):
                handle_aws_exception(exception=e, provider=self, directory=directory)

        listing = self.local_cache.directories.get(directory)
        if not listing:
            listing = DirectoryListing(directory=directory)
            self.local_cache.directories[directory] = listing

        item = DirectoryItem(
            directory=directory, name=name, value=secret,
            source=self.name
        )
        listing.add_item(item)
        if item.value is None:
            return None

        return item

    def retrieved_items_map(
            self, directory: DirectoryOrPath
    ) -> Optional[Mapping[str, DirectoryItem]]:
        directory = Directory.from_path(directory)
        listing = self.local_cache.directories.get(directory)
        if listing is None:
            return None
        return listing.item_mapping()
