#!/usr/bin/env python3
"""Test script to validate S3 migration.

Run this after configuring AWS credentials in .env file:
  python test_s3_migration.py
"""

import asyncio
import sys
from datetime import timedelta

from arbie.services.storage import get_storage_service


def test_sync_operations():
    """Test synchronous storage operations."""
    print("\n🔍 Testing sync operations...")

    storage = get_storage_service()
    session_id = "test-migration-session"
    test_file = "/workspace/test.txt"
    test_content = "Hello from AWS S3! Migration successful! 🎉"

    try:
        # Test write
        print("  → Writing file...")
        bytes_written = storage.write(test_file, test_content, session_id)
        assert bytes_written > 0, "Write returned 0 bytes"
        print(f"  ✓ Wrote {bytes_written} bytes")

        # Test exists
        print("  → Checking file exists...")
        assert storage.exists(test_file, session_id), "File should exist"
        print("  ✓ File exists")

        # Test read
        print("  → Reading file...")
        content = storage.read_text(test_file, session_id)
        assert content == test_content, f"Content mismatch: {content}"
        print(f"  ✓ Read content: {content[:50]}...")

        # Test get_file_info
        print("  → Getting file info...")
        info = storage.get_file_info(test_file, session_id)
        assert info.size > 0, "File size should be > 0"
        assert info.name == "test.txt", f"Name mismatch: {info.name}"
        print(f"  ✓ File info: {info.name}, {info.size} bytes")

        # Test list_files
        print("  → Listing files...")
        files = storage.list_files("/workspace/", session_id)
        assert len(files) > 0, "Should find at least 1 file"
        assert any(f.name == "test.txt" for f in files), "test.txt not in list"
        print(f"  ✓ Found {len(files)} file(s)")

        # Test presigned URL
        print("  → Generating presigned URL...")
        url = storage.get_signed_url(test_file, session_id, expires_in=timedelta(hours=1))
        assert url.startswith("https://"), f"Invalid URL: {url}"
        assert "arbie-files" in url, "Bucket name not in URL"
        print(f"  ✓ URL: {url[:80]}...")

        # Test delete
        print("  → Deleting file...")
        deleted = storage.delete(test_file, session_id)
        assert deleted, "Delete should return True"
        assert not storage.exists(test_file, session_id), "File should not exist after delete"
        print("  ✓ File deleted")

        print("✅ All sync operations passed!\n")
        return True

    except Exception as e:
        print(f"❌ Sync test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


async def test_async_operations():
    """Test asynchronous storage operations."""
    print("🔍 Testing async operations...")

    storage = get_storage_service()
    session_id = "test-async-session"
    test_file = "/workspace/async-test.txt"
    test_content = "Async S3 operations work! 🚀"

    try:
        # Test async write
        print("  → Writing file (async)...")
        bytes_written = await storage.write_async(test_file, test_content, session_id)
        assert bytes_written > 0, "Async write returned 0 bytes"
        print(f"  ✓ Wrote {bytes_written} bytes")

        # Test async read
        print("  → Reading file (async)...")
        content_bytes = await storage.read_async(test_file, session_id)
        content = content_bytes.decode("utf-8")
        assert content == test_content, f"Content mismatch: {content}"
        print(f"  ✓ Read content: {content[:50]}...")

        # Cleanup
        print("  → Cleaning up...")
        storage.delete(test_file, session_id)
        print("  ✓ Cleanup complete")

        print("✅ All async operations passed!\n")
        return True

    except Exception as e:
        print(f"❌ Async test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await storage.close()


def test_error_handling():
    """Test error handling for non-existent files."""
    print("🔍 Testing error handling...")

    storage = get_storage_service()
    session_id = "test-error-session"
    nonexistent_file = "/workspace/does-not-exist.txt"

    try:
        # Test exists on non-existent file
        print("  → Checking non-existent file...")
        assert not storage.exists(nonexistent_file, session_id), "Should return False"
        print("  ✓ exists() returns False for non-existent file")

        # Test read raises FileNotFoundError
        print("  → Reading non-existent file...")
        try:
            storage.read(nonexistent_file, session_id)
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError as e:
            print(f"  ✓ FileNotFoundError raised: {e}")

        # Test delete on non-existent file
        print("  → Deleting non-existent file...")
        deleted = storage.delete(nonexistent_file, session_id)
        assert not deleted, "Should return False"
        print("  ✓ delete() returns False for non-existent file")

        print("✅ All error handling tests passed!\n")
        return True

    except Exception as e:
        print(f"❌ Error handling test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("AWS S3 Migration Test Suite")
    print("=" * 60)

    results = []

    # Run sync tests
    results.append(("Sync Operations", test_sync_operations()))

    # Run async tests
    results.append(("Async Operations", asyncio.run(test_async_operations())))

    # Run error handling tests
    results.append(("Error Handling", test_error_handling()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")

    all_passed = all(result[1] for result in results)

    if all_passed:
        print("\n🎉 All tests passed! S3 migration successful!")
        print("\nNext steps:")
        print("1. Deploy to Tower.dev: tower deploy")
        print("2. Test end-to-end email flow")
        print("3. Monitor for any issues")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please check your AWS configuration:")
        print("1. Verify AWS credentials in .env")
        print("2. Ensure S3 bucket exists: aws s3 mb s3://arbie-files")
        print("3. Check AWS permissions")
        sys.exit(1)


if __name__ == "__main__":
    main()
