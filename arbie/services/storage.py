"""Azure Blob Storage service for Arbie file system.

Provides a virtual file system abstraction over Azure Blob Storage.
Replaces the non-existent tower.files API.

Virtual path structure:
- /attachments/{file} -> {session_id}/attachments/{file}
- /extracted/{file} -> {session_id}/extracted/{file}
- /workspace/{file} -> {session_id}/workspace/{file}
- /outputs/{file} -> {session_id}/outputs/{file}
"""

import asyncio
import io
import os
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import BinaryIO

from azure.identity import ClientSecretCredential, DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContainerClient, ContentSettings
from azure.storage.blob.aio import BlobServiceClient as AsyncBlobServiceClient
from azure.core.exceptions import ResourceNotFoundError


# Configuration from environment
STORAGE_ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME", "arbiefiles")
CONTAINER_NAME = "arbie-files"


@dataclass
class FileInfo:
    """Metadata about a file in storage."""

    name: str
    path: str
    size: int
    modified: datetime
    content_type: str | None = None


class StorageService:
    """Azure Blob Storage service with virtual path abstraction.

    Provides a session-scoped file system where virtual paths like
    /attachments/doc.pdf are translated to blob paths like
    {session_id}/attachments/doc.pdf.
    """

    def __init__(self, account_name: str = STORAGE_ACCOUNT_NAME):
        """Initialize storage service.

        Args:
            account_name: Azure Storage account name.
        """
        self.account_name = account_name
        self.account_url = f"https://{account_name}.blob.core.windows.net"
        self._client: BlobServiceClient | None = None
        self._async_client: AsyncBlobServiceClient | None = None

    def _get_credential(self):
        """Get Azure credential for authentication.

        Uses service principal if environment variables are set,
        otherwise falls back to DefaultAzureCredential.
        """
        client_id = os.getenv("AZURE_CLIENT_ID")
        client_secret = os.getenv("AZURE_CLIENT_SECRET")
        tenant_id = os.getenv("AZURE_TENANT_ID")

        if client_id and client_secret and tenant_id:
            return ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
            )
        return DefaultAzureCredential()

    @property
    def client(self) -> BlobServiceClient:
        """Get or create sync blob service client."""
        if self._client is None:
            self._client = BlobServiceClient(
                account_url=self.account_url,
                credential=self._get_credential(),
            )
        return self._client

    @property
    def container(self) -> ContainerClient:
        """Get container client, creating container if needed."""
        container = self.client.get_container_client(CONTAINER_NAME)
        try:
            container.get_container_properties()
        except ResourceNotFoundError:
            container.create_container()
        return container

    async def _get_async_client(self) -> AsyncBlobServiceClient:
        """Get or create async blob service client."""
        if self._async_client is None:
            self._async_client = AsyncBlobServiceClient(
                account_url=self.account_url,
                credential=self._get_credential(),
            )
        return self._async_client

    def _virtual_to_blob_path(self, virtual_path: str, session_id: str) -> str:
        """Translate virtual path to blob path.

        Args:
            virtual_path: Virtual path like /attachments/doc.pdf
            session_id: Session ID for scoping

        Returns:
            Blob path like {session_id}/attachments/doc.pdf
        """
        # Normalize path
        path = virtual_path.strip()
        if path.startswith("/"):
            path = path[1:]

        # Validate path starts with known prefix
        valid_prefixes = ("attachments/", "extracted/", "workspace/", "outputs/")
        if not any(path.startswith(p) for p in valid_prefixes):
            raise ValueError(
                f"Invalid virtual path: {virtual_path}. "
                f"Must start with one of: {valid_prefixes}"
            )

        return f"{session_id}/{path}"

    def _blob_to_virtual_path(self, blob_path: str, session_id: str) -> str:
        """Translate blob path back to virtual path.

        Args:
            blob_path: Blob path like {session_id}/attachments/doc.pdf
            session_id: Session ID for scoping

        Returns:
            Virtual path like /attachments/doc.pdf
        """
        prefix = f"{session_id}/"
        if blob_path.startswith(prefix):
            return "/" + blob_path[len(prefix) :]
        return "/" + blob_path

    def read(self, virtual_path: str, session_id: str) -> bytes:
        """Read file content from storage.

        Args:
            virtual_path: Virtual path to the file
            session_id: Session ID for scoping

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        blob_path = self._virtual_to_blob_path(virtual_path, session_id)
        blob_client = self.container.get_blob_client(blob_path)

        try:
            download = blob_client.download_blob()
            return download.readall()
        except ResourceNotFoundError:
            raise FileNotFoundError(f"File not found: {virtual_path}")

    def read_text(self, virtual_path: str, session_id: str, encoding: str = "utf-8") -> str:
        """Read file content as text.

        Args:
            virtual_path: Virtual path to the file
            session_id: Session ID for scoping
            encoding: Text encoding (default: utf-8)

        Returns:
            File content as string
        """
        content = self.read(virtual_path, session_id)
        return content.decode(encoding)

    def write(
        self,
        virtual_path: str,
        content: bytes | str | BinaryIO,
        session_id: str,
        content_type: str | None = None,
    ) -> int:
        """Write content to storage.

        Args:
            virtual_path: Virtual path to write to
            session_id: Session ID for scoping
            content: Content to write (bytes, str, or file-like object)
            content_type: Optional MIME type

        Returns:
            Number of bytes written
        """
        blob_path = self._virtual_to_blob_path(virtual_path, session_id)
        blob_client = self.container.get_blob_client(blob_path)

        # Convert string to bytes
        if isinstance(content, str):
            content = content.encode("utf-8")
            if content_type is None:
                content_type = "text/plain; charset=utf-8"

        # Handle file-like objects
        if hasattr(content, "read"):
            data = content.read()
        else:
            data = content

        blob_client.upload_blob(
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type) if content_type else None,
        )

        return len(data) if isinstance(data, (bytes, str)) else 0

    async def write_async(
        self,
        virtual_path: str,
        content: bytes | str,
        session_id: str,
        content_type: str | None = None,
    ) -> int:
        """Async write content to storage.

        Args:
            virtual_path: Virtual path to write to
            session_id: Session ID for scoping
            content: Content to write (bytes or str)
            content_type: Optional MIME type

        Returns:
            Number of bytes written
        """
        blob_path = self._virtual_to_blob_path(virtual_path, session_id)

        # Convert string to bytes
        if isinstance(content, str):
            content = content.encode("utf-8")
            if content_type is None:
                content_type = "text/plain; charset=utf-8"

        async_client = await self._get_async_client()
        container = async_client.get_container_client(CONTAINER_NAME)

        # Ensure container exists
        try:
            await container.get_container_properties()
        except ResourceNotFoundError:
            await container.create_container()

        blob_client = container.get_blob_client(blob_path)
        await blob_client.upload_blob(
            content,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type) if content_type else None,
        )

        return len(content)

    async def read_async(self, virtual_path: str, session_id: str) -> bytes:
        """Async read file content from storage.

        Args:
            virtual_path: Virtual path to the file
            session_id: Session ID for scoping

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        blob_path = self._virtual_to_blob_path(virtual_path, session_id)

        async_client = await self._get_async_client()
        container = async_client.get_container_client(CONTAINER_NAME)
        blob_client = container.get_blob_client(blob_path)

        try:
            download = await blob_client.download_blob()
            return await download.readall()
        except ResourceNotFoundError:
            raise FileNotFoundError(f"File not found: {virtual_path}")

    def list_files(
        self,
        virtual_path: str,
        session_id: str,
        recursive: bool = False,
    ) -> list[FileInfo]:
        """List files in a virtual directory.

        Args:
            virtual_path: Virtual directory path (e.g., /attachments/)
            session_id: Session ID for scoping
            recursive: If True, list all files recursively

        Returns:
            List of FileInfo objects
        """
        # Normalize path
        path = virtual_path.strip()
        if path.startswith("/"):
            path = path[1:]
        if path and not path.endswith("/"):
            path = path + "/"

        # Build blob prefix
        prefix = f"{session_id}/{path}" if path else f"{session_id}/"

        results = []
        seen_dirs = set()

        for blob in self.container.list_blobs(name_starts_with=prefix):
            # Get relative path from the prefix
            rel_path = blob.name[len(prefix) :]

            if not recursive:
                # For non-recursive, only show immediate children
                if "/" in rel_path:
                    # This is in a subdirectory - show the directory
                    dir_name = rel_path.split("/")[0]
                    if dir_name not in seen_dirs:
                        seen_dirs.add(dir_name)
                        results.append(
                            FileInfo(
                                name=dir_name,
                                path=f"/{path}{dir_name}/",
                                size=0,
                                modified=datetime.now(),
                                content_type="directory",
                            )
                        )
                else:
                    # Immediate file
                    results.append(
                        FileInfo(
                            name=rel_path,
                            path=f"/{path}{rel_path}",
                            size=blob.size,
                            modified=blob.last_modified,
                            content_type=blob.content_settings.content_type,
                        )
                    )
            else:
                # Recursive - show all files
                results.append(
                    FileInfo(
                        name=blob.name.split("/")[-1],
                        path=self._blob_to_virtual_path(blob.name, session_id),
                        size=blob.size,
                        modified=blob.last_modified,
                        content_type=blob.content_settings.content_type,
                    )
                )

        return results

    def exists(self, virtual_path: str, session_id: str) -> bool:
        """Check if a file exists.

        Args:
            virtual_path: Virtual path to check
            session_id: Session ID for scoping

        Returns:
            True if file exists
        """
        blob_path = self._virtual_to_blob_path(virtual_path, session_id)
        blob_client = self.container.get_blob_client(blob_path)
        return blob_client.exists()

    def delete(self, virtual_path: str, session_id: str) -> bool:
        """Delete a file.

        Args:
            virtual_path: Virtual path to delete
            session_id: Session ID for scoping

        Returns:
            True if file was deleted, False if it didn't exist
        """
        blob_path = self._virtual_to_blob_path(virtual_path, session_id)
        blob_client = self.container.get_blob_client(blob_path)

        try:
            blob_client.delete_blob()
            return True
        except ResourceNotFoundError:
            return False

    def get_file_info(self, virtual_path: str, session_id: str) -> FileInfo:
        """Get metadata about a file.

        Args:
            virtual_path: Virtual path to the file
            session_id: Session ID for scoping

        Returns:
            FileInfo with file metadata

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        blob_path = self._virtual_to_blob_path(virtual_path, session_id)
        blob_client = self.container.get_blob_client(blob_path)

        try:
            props = blob_client.get_blob_properties()
            return FileInfo(
                name=blob_path.split("/")[-1],
                path=virtual_path,
                size=props.size,
                modified=props.last_modified,
                content_type=props.content_settings.content_type,
            )
        except ResourceNotFoundError:
            raise FileNotFoundError(f"File not found: {virtual_path}")

    async def close(self):
        """Close async client connections."""
        if self._async_client:
            await self._async_client.close()
            self._async_client = None


# Singleton instance
_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    """Get the singleton storage service instance."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
