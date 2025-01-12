import logging
from pathlib import Path
import tempfile

from config import ssm_params
from utils import send_to_quarantine_bucket
from utils import get_file_extension
from utils import validate_filetype
from utils import add_tags
from utils import create_tags_for_file_validation
from utils import extract_zipfile


logger = logging.getLogger()


# TODO: What bucket should be used when a file is determined to be invalid?


def validate_file(bucket: str, key: str, file_path: str, receipt_handle: str, approved_filetypes: list):
    try:
        file_ext = get_file_extension(file_path)
        valid, tags = validate_filetype(file_path, file_ext, approved_filetypes)  # noqa: E501
        add_tags(bucket, key, tags)

        if not valid:
            quarantine_bucket = ssm_params["/pipeline/QuarantineBucketName"]
            send_to_quarantine_bucket(bucket, quarantine_bucket, key, receipt_handle)  # noqa: E501
            return False

        if not get_file_extension(file_path) == "zip":
            return True

        # TODO: What files are allowed to be in a zip file? For example, is an XML allowed?
        logger.info(f"The file is a zip file. Validating its contents")

        with tempfile.TemporaryDirectory() as tmpdir:
            extract_zipfile(file_path, tmpdir)
            file_paths = [str(item) for item in Path(tmpdir).rglob("*") if item.is_file()]  # noqa: E501
            for _file_path in file_paths:
                # Nested zip files are not allowed, for now
                _file_ext = get_file_extension(_file_path)
                if _file_ext == "zip":
                    logger.warning(f"Nested zip files are not allowed: {_file_path}")  # noqa: E501
                    error_tags = create_tags_for_file_validation("NestedZipFileNotAllowed", "zip", "application/zip")  # noqa: E501
                    add_tags(bucket, key, error_tags)
                    quarantine_bucket = ssm_params["/pipeline/QuarantineBucketName"]
                    send_to_quarantine_bucket(bucket, quarantine_bucket, key, receipt_handle)  # noqa: E501
                    return False

                valid, _ = validate_filetype(_file_path, _file_ext, approved_filetypes)  # noqa: E501
                if not valid:
                    # If one file fails validation, move the entire zip file to quarantine bucket
                    error_tags = create_tags_for_file_validation("ZipFileWithInvalidFile", "zip", "application/zip")  # noqa: E501
                    add_tags(bucket, key, error_tags)
                    quarantine_bucket = ssm_params["/pipeline/QuarantineBucketName"]
                    send_to_quarantine_bucket(bucket, quarantine_bucket, key, receipt_handle)  # noqa: E501
                    return False

        return True

    except Exception as e:
        # TODO: What should happen in case of errors? Is logging it out enough? That means the SQS message will be processed again
        logger.error(f"Could not validate the file: {e}")
        raise
        # quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")  # noqa: E501
        # send_to_quarantine_bucket(bucket, quarantine_bucket, key, receipt_handle)  # noqa: E501
