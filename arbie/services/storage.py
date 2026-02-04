"""AWS S3 storage service for Arbie file system.

Provides a virtual file system abstraction over AWS S3.
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
from datetime import datetime, timedelta
from functools import lru_cache
from typing import BinaryIO

import boto3
import aioboto3
from botocore.exceptions import ClientError, NoCredentialsError


# Configuration from environment
S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME", "arbie-files")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


@dataclass
class FileInfo:
    """Metadata about a file in storage."""

    name: str
    path: str
    size: int
    modified: datetime
    content_type: str | None = None


class StorageService:
    """AWS S3 storage service with virtual path abstraction.

    Provides a session-scoped file system where virtual paths like
    /attachments/doc.pdf are translated to S3 object keys like
    {session_id}/attachments/doc.pdf.
    """

    def __init__(self, bucket_name: str = S3_BUCKET_NAME):
        """Initialize storage service.

        Args:
            bucket_name: S3 bucket name.
        """
        self.bucket_name = bucket_name
        self._client = None  # boto3.client('s3')
        self._async_session = None  # aioboto3.Session()

    @property
    def client(self):
        """Get or create sync S3 client."""
        if self._client is None:
            # AWS SDK automatically uses credentials chain
            self._client = boto3.client('s3', region_name=AWS_REGION)
            # Ensure bucket exists
            self._ensure_bucket_exists()
        return self._client

    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist."""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                # Bucket doesn't exist - create it
                if AWS_REGION == 'us-east-1':
                    # us-east-1 doesn't accept LocationConstraint
                    self.client.create_bucket(Bucket=self.bucket_name)
                else:
                    self.client.create_bucket(
                        Bucket=self.bucket_name,
                        CreateBucketConfiguration={'LocationConstraint': AWS_REGION}
                    )
            else:
                raise

    async def _get_async_session(self):
        """Get or create async aioboto3 session."""
        if self._async_session is None:
            self._async_session = aioboto3.Session()
        return self._async_session

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
        object_key = self._virtual_to_blob_path(virtual_path, session_id)
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=object_key)
            return response['Body'].read()
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise FileNotFoundError(f"File not found: {virtual_path}")
            raise

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
        object_key = self._virtual_to_blob_path(virtual_path, session_id)

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

        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type

        self.client.put_object(
            Bucket=self.bucket_name,
            Key=object_key,
            Body=data,
            **extra_args
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
        object_key = self._virtual_to_blob_path(virtual_path, session_id)

        # Convert string to bytes
        if isinstance(content, str):
            content = content.encode("utf-8")
            if content_type is None:
                content_type = "text/plain; charset=utf-8"

        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type

        session = await self._get_async_session()
        async with session.client('s3', region_name=AWS_REGION) as s3:
            await s3.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=content,
                **extra_args
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
        object_key = self._virtual_to_blob_path(virtual_path, session_id)

        session = await self._get_async_session()
        async with session.client('s3', region_name=AWS_REGION) as s3:
            try:
                response = await s3.get_object(Bucket=self.bucket_name, Key=object_key)
                async with response['Body'] as stream:
                    return await stream.read()
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    raise FileNotFoundError(f"File not found: {virtual_path}")
                raise

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

        # S3 pagination
        paginator = self.client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)

        for page in pages:
            for obj in page.get('Contents', []):
                # Get relative path from the prefix
                rel_path = obj['Key'][len(prefix):]

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
                                size=obj['Size'],
                                modified=obj['LastModified'],
                                content_type=obj.get('ContentType'),
                            )
                        )
                else:
                    # Recursive - show all files
                    results.append(
                        FileInfo(
                            name=obj['Key'].split("/")[-1],
                            path=self._blob_to_virtual_path(obj['Key'], session_id),
                            size=obj['Size'],
                            modified=obj['LastModified'],
                            content_type=obj.get('ContentType'),
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
        object_key = self._virtual_to_blob_path(virtual_path, session_id)
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise

    def delete(self, virtual_path: str, session_id: str) -> bool:
        """Delete a file.

        Args:
            virtual_path: Virtual path to delete
            session_id: Session ID for scoping

        Returns:
            True if file was deleted, False if it didn't exist
        """
        object_key = self._virtual_to_blob_path(virtual_path, session_id)
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return False
            raise

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
        object_key = self._virtual_to_blob_path(virtual_path, session_id)
        try:
            response = self.client.head_object(Bucket=self.bucket_name, Key=object_key)
            return FileInfo(
                name=object_key.split("/")[-1],
                path=virtual_path,
                size=response['ContentLength'],
                modified=response['LastModified'],
                content_type=response.get('ContentType'),
            )
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise FileNotFoundError(f"File not found: {virtual_path}")
            raise

    def get_signed_url(
        self,
        virtual_path: str,
        session_id: str,
        expires_in: timedelta = timedelta(hours=1),
        permissions = None,
    ) -> str:
        """Generate a presigned URL for public access to a file.

        Args:
            virtual_path: Virtual path to the file.
            session_id: Session ID for scoping.
            expires_in: How long the URL should be valid (default: 1 hour).
            permissions: Ignored for S3 (always read-only).

        Returns:
            Presigned URL that provides public access to the file.

        Raises:
            FileNotFoundError: If file doesn't exist.
        """
        object_key = self._virtual_to_blob_path(virtual_path, session_id)

        # Verify file exists
        if not self.exists(virtual_path, session_id):
            raise FileNotFoundError(f"File not found: {virtual_path}")

        # Generate presigned URL
        expires_seconds = int(expires_in.total_seconds())

        url = self.client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': self.bucket_name,
                'Key': object_key
            },
            ExpiresIn=expires_seconds
        )

        return url

    async def close(self):
        """Close async client connections."""
        if self._async_session:
            await self._async_session.close()
            self._async_session = None


# Singleton instance
_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    """Get the singleton storage service instance."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
