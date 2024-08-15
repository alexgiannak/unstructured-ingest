from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generator, Optional, Union

from pydantic import Field, Secret

from unstructured_ingest.utils.dep_check import requires_dependencies
from unstructured_ingest.utils.string_and_date_utils import json_to_dict
from unstructured_ingest.v2.interfaces import DownloadResponse, FileData, UploadContent
from unstructured_ingest.v2.processes.connector_registry import (
    DestinationRegistryEntry,
    SourceRegistryEntry,
)
from unstructured_ingest.v2.processes.connectors.fsspec.fsspec import (
    FsspecAccessConfig,
    FsspecConnectionConfig,
    FsspecDownloader,
    FsspecDownloaderConfig,
    FsspecIndexer,
    FsspecIndexerConfig,
    FsspecUploader,
    FsspecUploaderConfig,
)

CONNECTOR_TYPE = "gcs"


class GcsIndexerConfig(FsspecIndexerConfig):
    pass


service_account_key_description = """
  Options:
  - ``None``, GCSFS will attempt to guess your credentials in the
following order: gcloud CLI default, gcsfs cached token, google compute
metadata service, anonymous.
  - ``'google_default'``, your default gcloud credentials will be used,
    which are typically established by doing ``gcloud login`` in a terminal.
  - ``'cache'``, credentials from previously successful gcsfs
    authentication will be used (use this after "browser" auth succeeded)
  - ``'anon'``, no authentication is performed, and you can only
    access data which is accessible to allUsers (in this case, the project and
    access level parameters are meaningless)
  - ``'browser'``, you get an access code with which you can
    authenticate via a specially provided URL
  - if ``'cloud'``, we assume we are running within google compute
    or google container engine, and query the internal metadata directly for
    a token.
  - you may supply a token generated by the
    [gcloud](https://cloud.google.com/sdk/docs/)
    utility; this is either a python dictionary or the name of a file
    containing the JSON returned by logging in with the gcloud CLI tool.
  """


class GcsAccessConfig(FsspecAccessConfig):
    service_account_key: Optional[str] = Field(
        default=None, description=service_account_key_description
    )
    token: Union[str, dict, None] = Field(init=False, default=None)

    def model_post_init(self, __context: Any) -> None:
        ALLOWED_AUTH_VALUES = "google_default", "cache", "anon", "browser", "cloud"

        # Case: null value
        if not self.service_account_key:
            return

        # Case: one of auth constants
        if self.service_account_key in ALLOWED_AUTH_VALUES:
            self.token = self.service_account_key
            return

        # Case: token as json
        if isinstance(json_to_dict(self.service_account_key), dict):
            self.token = json_to_dict(self.service_account_key)
            return

        # Case: path to token
        if Path(self.service_account_key).is_file():
            self.token = self.service_account_key
            return

        raise ValueError("Invalid auth token value")


SecretGcsAccessConfig = Secret[GcsAccessConfig]


class GcsConnectionConfig(FsspecConnectionConfig):
    supported_protocols: list[str] = field(default_factory=lambda: ["gs", "gcs"], init=False)
    access_config: SecretGcsAccessConfig = Field(
        default_factory=lambda: SecretGcsAccessConfig(secret_value=GcsAccessConfig())
    )
    connector_type: str = Field(default=CONNECTOR_TYPE, init=False)


@dataclass
class GcsIndexer(FsspecIndexer):
    connection_config: GcsConnectionConfig
    index_config: GcsIndexerConfig
    connector_type: str = CONNECTOR_TYPE

    @requires_dependencies(["gcsfs", "fsspec"], extras="gcs")
    def run(self, **kwargs: Any) -> Generator[FileData, None, None]:
        return super().run(**kwargs)

    @requires_dependencies(["gcsfs", "fsspec"], extras="gcs")
    def precheck(self) -> None:
        super().precheck()


class GcsDownloaderConfig(FsspecDownloaderConfig):
    pass


@dataclass
class GcsDownloader(FsspecDownloader):
    protocol: str = "gcs"
    connection_config: GcsConnectionConfig
    connector_type: str = CONNECTOR_TYPE
    download_config: Optional[GcsDownloaderConfig] = field(default_factory=GcsDownloaderConfig)

    @requires_dependencies(["gcsfs", "fsspec"], extras="gcs")
    def run(self, file_data: FileData, **kwargs: Any) -> DownloadResponse:
        return super().run(file_data=file_data, **kwargs)

    @requires_dependencies(["gcsfs", "fsspec"], extras="gcs")
    async def run_async(self, file_data: FileData, **kwargs: Any) -> DownloadResponse:
        return await super().run_async(file_data=file_data, **kwargs)


class GcsUploaderConfig(FsspecUploaderConfig):
    pass


@dataclass
class GcsUploader(FsspecUploader):
    connector_type: str = CONNECTOR_TYPE
    connection_config: GcsConnectionConfig
    upload_config: GcsUploaderConfig = field(default=None)

    @requires_dependencies(["gcsfs", "fsspec"], extras="gcs")
    def __post_init__(self):
        super().__post_init__()

    @requires_dependencies(["gcsfs", "fsspec"], extras="gcs")
    def precheck(self) -> None:
        super().precheck()

    @requires_dependencies(["gcsfs", "fsspec"], extras="gcs")
    def run(self, contents: list[UploadContent], **kwargs: Any) -> None:
        return super().run(contents=contents, **kwargs)

    @requires_dependencies(["gcsfs", "fsspec"], extras="gcs")
    async def run_async(self, path: Path, file_data: FileData, **kwargs: Any) -> None:
        return await super().run_async(path=path, file_data=file_data, **kwargs)


gcs_source_entry = SourceRegistryEntry(
    indexer=GcsIndexer,
    indexer_config=GcsIndexerConfig,
    downloader=GcsDownloader,
    downloader_config=GcsDownloaderConfig,
    connection_config=GcsConnectionConfig,
)

gcs_destination_entry = DestinationRegistryEntry(
    uploader=GcsUploader,
    uploader_config=GcsUploaderConfig,
    connection_config=GcsConnectionConfig,
)
