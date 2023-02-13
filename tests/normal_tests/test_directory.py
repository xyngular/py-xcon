from xcon.directory import Directory


def test_normal_directory_is_not_formatted():
    directory = Directory(path='/static/non-formatted/path')
    assert directory.is_path_format is False
    assert directory.path == '/static/non-formatted/path'
    assert directory.service == 'static'
    assert directory.env == 'non-formatted/path'


def test_format_directory_is_formatted():
    directory = Directory(path='/{service}/formatted/{environment}')
    assert directory.is_path_format is True
    assert directory.path == '/{service}/formatted/{environment}'
    assert directory.service == '{service}'
    assert directory.env == 'formatted/{environment}'


def test_resolved_directory_with_format():
    directory = Directory(path='/{service}/formatted/{environment}')
    resolved = directory.resolve(service='my-service', environment='my-environment')
    assert resolved.is_path_format is False
    assert resolved.path == '/my-service/formatted/my-environment'
    assert resolved.service == 'my-service'
    assert resolved.env == 'formatted/my-environment'

    assert directory.is_path_format is True
    assert directory.path == '/{service}/formatted/{environment}'
    assert directory.service == '{service}'
    assert directory.env == 'formatted/{environment}'


def test_directory_hash_in_set():
    formatted_dir = Directory(path='/{service}/formatted/{environment}')
    resolved_dir = formatted_dir.resolve(service='my-service', environment='my-environment')
    nonformatted_dir = Directory(path='/{service}/formatted/{environment}', is_path_format=False)

    # If it's marked as non-formatted (even if it has format-style directives in it),
    # it should not format it:
    assert nonformatted_dir.resolve(service='s', environment='e') is nonformatted_dir

    # They should all look unique to each-other.
    dir_set = {formatted_dir, resolved_dir, nonformatted_dir}
    assert len(dir_set) == 3

