from __future__ import annotations

from typing import Optional, Mapping

from xboto import boto_clients

from xcon.provider import AwsProvider, ProviderChain

from .common import handle_aws_exception
from ..directory import Directory, DirectoryListing, DirectoryOrPath, DirectoryItem, DirectoryChain


class SsmParamStoreProvider(AwsProvider):
    attributes_to_skip_while_copying = ['_store_get_params_paginator']
    name = "ssm"
    _store_get_params_paginator = None

    @property
    def _get_params_paginator(self):
        paginator = self._store_get_params_paginator
        if not paginator:
            paginator = boto_clients.ssm.get_paginator('get_parameters_by_path')
            self._store_get_params_paginator = paginator
        return paginator

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
        return self._item_only_for_directory(name=name, directory=directory)

    def _item_only_for_directory(
            self, name: str, directory: DirectoryOrPath
    ) -> Optional[DirectoryItem]:
        directory = Directory.from_path(directory)
        if not directory:
            return None

        listing = self.local_cache.get(directory)
        if listing:
            return listing.get_item(name)

        items = []
        try:
            # We need to lookup the directory listing from Secrets Manager.
            pages = self._get_params_paginator.paginate(
                Path=directory.path,
                Recursive=False,
                WithDecryption=True,
            )

            for p in pages:
                for item_info in p['Parameters']:
                    item_path: str = item_info['Name']
                    item = DirectoryItem(
                        directory=directory,
                        name=item_path.split("/")[-1],
                        value=item_info['Value'],
                        source=self.name
                    )
                    items.append(item)
        except Exception as e:
            # This will either re-raise error....
            # or handle it and we will continue/ignore the error.
            handle_aws_exception(e, self, directory)

        # If we got an error, `items` will be empty.
        # In this case, in the future, we won't try to retrieve this directory since we are
        # setting it blank here.
        listing = DirectoryListing(directory=directory, items=items)

        self.log_about_items(
            items=listing.item_mapping().values(),
            path=listing.directory.path
        )

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
