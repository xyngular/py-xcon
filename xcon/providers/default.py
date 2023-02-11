from typing import List, Type
from .environmental import EnvironmentalProvider
from .ssm_param_store import SsmParamStoreProvider
from .secrets_manager import SecretsManagerProvider
from ..provider import Provider


default_provider_types: List[Type[Provider]] = [
    # Order is important
    EnvironmentalProvider,
    SecretsManagerProvider,
    SsmParamStoreProvider
]
""" Set of default provider types and order to use them in for `xcon.config.Config`.
"""
