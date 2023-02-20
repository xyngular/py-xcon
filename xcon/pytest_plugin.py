"""
Shared common fixtures for helping with unit-testing.

.. important:: Very Important!  Don't import this module your self!
    pytest should automatically import this via it's plugin mechanism.
    If you import any of the fixtures below manually, you may get something like this:

    `ValueError: duplicate 'xyn_context'`

    You should be able to use any of these fixtures without importing them yourself.

    This is accomplished via the setup.py file in xcon, it tells pytest about the
    `xcon.pytest_plugin` module so it can load them automatically.

"""
from __future__ import annotations

import pytest

from xcon.providers import EnvironmentalProvider
from xcon import Config
from xcon import xcon_settings


@pytest.fixture(autouse=True)
def xcon_test_config(xinject_test_context):
    """
    Important: This fixture should automatically be imported and auto-used as long as
    `xcon` is installed as a dependency in any project.

    This fixture is automatically used for each unit-test.

    It configures the config object used by default in the unit tests to only use
    the environmental provider and to disable use of the cacher.

    This fixture also pre-sets the SERVICE_NAME and APP_ENV on the config, which effects how
    the config object will use for it's default Directories:
        SERVICE_NAME='testing'
        APP_ENV='unit'

    A good general way to change Config xcon_settings during unit tests is to simply set them on
    the default `Config` object:

    >>> from xcon import config
    >>> from xyn_types import Default
    >>>
    >>> def text_something():
    ...     # Re-enables the cacher by default for `config`:
    ...     config.cacher = Default

    Or you can create a new Config object, and activate it via decorator:

    >>> from xcon import config, Config
    >>> from xcon.providers import DynamoCacher
    >>>
    >>> # Create a new Config object with desired xcon_settings and then make it the current one!
    >>> # In this case, we enable the cacher explicitly (not using `Default` here).
    >>> # See `XCON_DISABLE_DEFAULT_CACHER` in the README.md for more details.
    >>> @Config(cacher=DynamoCacher):
    >>> def test_something():
    ...    assert isinstance(config.resolved_cacher, DynamoCacher)

    Or you can create a new Config object and activate/make-it-current via a with statement:

    >>> from xcon import config, Config
    >>> from xcon.providers import DynamoCacher
    >>>
    >>> def test_something():
    ...    # Check default unit-test config:
    ...    assert config.resolved_cacher is None
    ...
    ...    # Activate new Config xcon_settings:
    ...    with Config(cacher=DynamoCacher):
    ...         assert isinstance(config.resolved_cacher, DynamoCacher)

    When the unit tests are done, an automatically used autouse fixture at
    `xyn_resource.pytest_plugin.xyn_context` will before each unit test
    throw away all resources.

    This is nice because it helps guaratee any Config or other resource changes won't be
    leaked between unit tests in an easy way
    (ie: All you have to do is configure your resources per-unit-test run,
    and not at the module level).

    """
    # Have a base-line for each unit-test before it executes
    # (The xyn_context fixture throws always all resource objects before each test,
    #  so configuring config with base-line values before each unit test)
    _setup_config_for_testing()
    return Config.grab()


def _setup_config_for_testing():
    # Get config object from current/new context:
    config = Config.grab()

    # We default to ONLY use 'EnvironmentalProvider'.
    # We tell it not to use a cacher or parent, not testing those aspects in this test.
    xcon_settings.providers = [EnvironmentalProvider]

    # We have no providers, and so nothing should be cached....
    # But to be safe and make it obvious, explicitly disable cacher by default for unit-tests.
    config.cacher = None

    return config


# Setup a base-line for config before pytest collects the unit tests.
# This executes before any conftest.py, so it sets up a base-line,
# during import time of project py-test related files.
_setup_config_for_testing()
