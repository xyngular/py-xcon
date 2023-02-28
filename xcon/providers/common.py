import logging

from botocore import exceptions
from ..directory import Directory
from ..provider import AwsProvider

log = logging.getLogger(__name__)

aws_error_classes_to_ignore = {
    # If no aws credentials were found.
    exceptions.NoCredentialsError,
    exceptions.NoRegionError,
}

aws_error_codes_to_ignore = {
    # If app does not have permission to get a specific directory/path.
    'AccessDeniedException',

    # Not sure if I want to include these?
    'InvalidSignatureException',  # Probably aws access_key is wrong.
    'UnrecognizedClientException'  # When security token is invalid [probably wrong aws key_id].
    'ExpiredTokenException',  # When temporary creds are expired (from sso creds)

    # Example: If dynamo cache table does not exist; we want to ignore it and just move on...
    'ResourceNotFoundException'
}
""" List of error codes from boto to ignore. We log a warning, but continue on. """


def handle_aws_exception(exception: Exception, provider: AwsProvider, directory: Directory):
    """ Used by the `xcon.config.Config` providers that connect to AWS.
        A common set of code to handle exceptions that happen while getting configuration
        values from various AWS resources.

        If we ignore an error, we will log a warning, and then set the directory as
        an error'd directory via `log_ignored_aws_exception`; which in turn calls
        `xcon.provider.AwsProvider.mark_errored_directory` on the provider.
        This informs the provider so they don't keep asking for this directory in the future.
    """
    # First check to see if we have a specific `BotoCoreError` subclass of some sort...
    for ignored_error_class in aws_error_classes_to_ignore:
        if isinstance(exception, ignored_error_class):
            e_type = type(exception)
            log_ignored_aws_exception(
                exception=exception,
                provider=provider,
                directory=directory,
                error_detail=f"error class [{e_type.__module__}.{e_type.__name__}]"
            )
            return

    # Handle it if it's a client error...
    if not isinstance(exception, exceptions.ClientError):
        # We are not a ClientError, so re-raise exception.
        raise exception from None

    if not hasattr(exception, "response"):
        # For some reason, ClientError has no 'response' attribute, re-raise exception.
        raise exception from None

    response: dict = exception.response
    error = response.get('Error', {})
    code = error.get('Code')
    if code in aws_error_codes_to_ignore:
        log_ignored_aws_exception(
            exception=exception,
            provider=provider,
            directory=directory,
            error_detail=f"error code [{code}]"
        )
        return

    # We were unable to handle the exception, re-raise....
    raise exception from None


def log_ignored_aws_exception(
        exception: Exception, provider: AwsProvider, directory: Directory, error_detail: str
):
    """
        We will log a warning, and then set the directory as an error'd directory via
        `xcon.provider.AwsProvider.mark_errored_directory` on the provider.

        This informs the provider so they don't keep asking for this directory in the future.
    Args:
        exception: Exception that tells us about the error.
        provider (xcon.provider.AwsProvider): AwsProvider that had the error.
        directory (xcon.directory.Directory): Directory that had the error.
        error_detail: Some extra human redable details about the error.

    Returns:

    """
    log.warning(
        f"While getting config values via directory [{directory.path}] from aws via provider "
        f"[{provider.name}], encountered error that I will be ignoring due to {error_detail} "
        f"; exception details: [{exception}]"
    )

    # Mark directory as having an error, for informational purposes only.
    provider.mark_errored_directory(directory)
    if isinstance(exception, exceptions.BotoCoreError):
        provider.botocore_error_ignored_exception = exception
