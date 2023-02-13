from logging import getLogger

log = getLogger(__name__)


def ssm_or_secrets_change_event(event, context):
    """
    Here are examples of locations of the various paths from the various events we could get:

    detail->name->/auth/dev/db_port
    detail->responseElements->name->/test/prod/testing-experiment-2
    detail->requestParameters->name->/test/prod/testing-experiment-2

    detail->requestParameters->secretId->arn:aws:secretsmanager:
      us-east-1:972731226928:secret:/test/prod/testing-experiment-2-Pwqh7v

    detail->requestParameters->secretId->/test/dev/testing-experiment-2
    """
    detail = get_or_blank_dict(event, 'detail')
    path = detail.get('name')

    if not path:
        path = get_or_blank_dict(detail, 'responseElements').get('name')

    if not path:
        path = get_or_blank_dict(detail, 'requestParameters').get('name')

    if not path:
        path = get_or_blank_dict(detail, 'requestParameters').get('secretId')

    if not path:
        raise AttributeError(
            f"Could not find attribute with a path for event {event}.",
        )

    if ':' in path:
        # Paths should NEVER have a colon in them,
        # so this means we have a value that is in this format (all one line):
        #
        # arn:aws:secretsmanager:us-east-1:972731226928
        #   :secret:/test/joshorr/testing-experiment-2-Pwqh7v

        # This will extract the part of the ARN that is the path we care about.
        path = '-'.join(path.split(':')[-1].split('-')[0:-1])

    path_components = path.split('/')

    if len(path_components) <= 1:
        raise ValueError(
            f"Path ({path}) in event did not have at least two path components, "
            f"it instead had ({len(path_components)}; must have a directory and a var-name. "
            f"If it turns out we do have SSM/Secrets like this we want to keep then turn this "
            f"error into a warning instead.",
        )

    directory = '/'.join(path_components[0:-1])
    var_name = str(path_components[-1])

    query = {
        'real_name': var_name.lower(),  # names are always lower-case in config cache.
        'real_directory': ['/_nonExistent', directory]  # Directories keep their case.
    }

    log.info(
        f"From source ({event.get('source')}), "
        f"got a change event for path ({path}); "
        f"will query cache table with ({query}); "
        f"via event ({event}).",
        extra={'event': event, 'query': query, 'path': path}
    )

    # todo: Copy the query-boto-structure out of library for get/delete calls below.

    # items = ConfigCacheItem.api.get(query, allow_scan=True)
    #
    # items = list(items)
    # log.info(f'Deleting cached items: ({items})')
    # ConfigCacheItem.api.client.delete_objs(items)


def get_or_blank_dict(dict_value, key):
    if not dict_value:
        return {}

    if not isinstance(dict_value, dict):
        return {}

    value = dict_value.get(key, None)
    if not value:
        return {}

    if not isinstance(value, dict):
        return {}
    return value

