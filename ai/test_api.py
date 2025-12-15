"""
Test script for Excel to JSON Converter API
Run this after starting the server to test all endpoints
"""

import requests
import sys
from pathlib import Path

BASE_URL = "http://localhost:8000"


def test_health():
    """Test health check endpoint"""
    print("\n" + "="*60)
    print("Testing Health Check Endpoint")
    print("="*60)

    try:
        response = requests.get(f"{BASE_URL}/health")
        response.raise_for_status()

        data = response.json()
        print(f"Status: {data.get('status')}")
        print(f"Service: {data.get('service')}")
        print(f"Timestamp: {data.get('timestamp')}")
        print(f"Input Folder: {data.get('input_folder')}")
        print(f"Output Folder: {data.get('output_folder')}")
        print("\n✅ Health check passed!")
        return True

    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to server. Is it running?")
        print("Start the server with: ./run_server.sh")
        return False
    except Exception as e:
        print(f"\n❌ Health check failed: {e}")
        return False


def test_root():
    """Test root endpoint"""
    print("\n" + "="*60)
    print("Testing Root Endpoint")
    print("="*60)

    try:
        response = requests.get(f"{BASE_URL}/")
        response.raise_for_status()

        data = response.json()
        print(f"Message: {data.get('message')}")
        print(f"Version: {data.get('version')}")
        print(f"Endpoints: {data.get('endpoints')}")
        print("\n✅ Root endpoint passed!")
        return True

    except Exception as e:
        print(f"\n❌ Root endpoint failed: {e}")
        return False


def test_list_files():
    """Test list files endpoint"""
    print("\n" + "="*60)
    print("Testing List Files Endpoint")
    print("="*60)

    try:
        response = requests.get(f"{BASE_URL}/files")
        response.raise_for_status()

        data = response.json()
        print(f"Input Files: {data.get('total_input_files')}")
        print(f"Output Files: {data.get('total_output_files')}")

        if data.get('input_files'):
            print("\nInput Files:")
            for file in data.get('input_files', []):
                print(f"  - {file.get('filename')} ({file.get('size')} bytes)")

        if data.get('output_files'):
            print("\nOutput Files:")
            for file in data.get('output_files', [])[:5]:  # Show first 5
                print(f"  - {file.get('filename')} ({file.get('size')} bytes)")

        print("\n✅ List files endpoint passed!")
        return True

    except Exception as e:
        print(f"\n❌ List files endpoint failed: {e}")
        return False


def test_upload(file_path=None):
    """Test upload endpoint"""
    print("\n" + "="*60)
    print("Testing Upload Endpoint")
    print("="*60)

    if not file_path:
        print("⚠️  No file path provided, skipping upload test")
        print("Usage: python test_api.py /path/to/file.xlsx")
        return None

    file_path = Path(file_path)
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return False

    if not (file_path.suffix == '.xlsx' or file_path.suffix == '.xls'):
        print(f"❌ Invalid file format: {file_path.suffix}")
        print("Only .xlsx and .xls files are supported")
        return False

    try:
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            response = requests.post(f"{BASE_URL}/upload", files=files)
            response.raise_for_status()

        data = response.json()
        print(f"Message: {data.get('message')}")
        print(f"Filename: {data.get('filename')}")
        print(f"File Path: {data.get('file_path')}")
        print(f"File Size: {data.get('file_size')} bytes")
        print(f"Timestamp: {data.get('timestamp')}")
        print("\n✅ Upload endpoint passed!")
        return True

    except Exception as e:
        print(f"\n❌ Upload endpoint failed: {e}")
        return False


def test_convert():
    """Test convert endpoint"""
    print("\n" + "="*60)
    print("Testing Convert Endpoint")
    print("="*60)
    print("⚠️  This may take a while depending on file size...")

    try:
        response = requests.post(f"{BASE_URL}/convert", timeout=300)

        if response.status_code == 404:
            print("⚠️  No Excel files found in input folder")
            print("Upload a file first using: /upload endpoint")
            return None

        response.raise_for_status()

        data = response.json()
        print(f"Message: {data.get('message')}")
        print(f"Files Processed: {data.get('files_processed')}")
        print(f"Tables Extracted: {data.get('tables_extracted')}")
        print(f"Output Folder: {data.get('output_folder')}")

        if data.get('consolidated_results'):
            print(f"\nExtracted {len(data.get('consolidated_results'))} tables")
            print("First table preview:")
            first_table = data.get('consolidated_results')[0]
            print(f"  Sheet: {first_table.get('sheet_name')}")
            print(f"  Headers: {first_table.get('headers')}")
            print(f"  Rows: {len(first_table.get('rows', []))}")

        print("\n✅ Convert endpoint passed!")
        return True

    except requests.exceptions.Timeout:
        print("\n❌ Convert endpoint timed out (this is normal for large files)")
        return False
    except Exception as e:
        print(f"\n❌ Convert endpoint failed: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "#"*60)
    print("# Excel to JSON Converter API - Test Suite")
    print("#"*60)

    file_path = sys.argv[1] if len(sys.argv) > 1 else None

    results = {
        'health': test_health(),
        'root': test_root(),
        'list_files': test_list_files(),
        'upload': test_upload(file_path),
        'convert': test_convert() if file_path else None
    }

    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)

    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)

    for test, result in results.items():
        status = "✅ PASSED" if result is True else "❌ FAILED" if result is False else "⚠️  SKIPPED"
        print(f"{test.upper():15} : {status}")

    print("\n" + "-"*60)
    print(f"Total: {len(results)} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}")
    print("="*60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
