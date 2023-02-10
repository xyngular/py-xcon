import os

import pytest
from xyn_config import config

# have a semi-really looking environmental variable to test with.
os.environ["DJANGO_SETTINGS_MODULE"] = "somemodule.some_app.settings.tests"

service_name_at_import_time = str(config.SERVICE_NAME)
app_env_at_import_time = str(config.APP_ENV)


def test_ensure_config_is_at_baseline_at_module_import_time():
    # Ensure that config is configured at conftest import time.
    assert service_name_at_import_time == 'testing'
    assert app_env_at_import_time == 'unit'


@pytest.fixture
@pytest.mark.order(-70)
def directory(xyn_config):
    """ Returns the currently configured full test Directory [with the proper service/env set].
        This uses the `config` fixture to an isolated config, and `config` fixture will get
        an isolated Context for you as well.
    """
    from xyn_config.directory import Directory
    return Directory(service=xyn_config.SERVICE_NAME, env=xyn_config.APP_ENV)
