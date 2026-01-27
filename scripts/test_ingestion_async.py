import requests
import time
import os
import sys
from pathlib import Path
import json

API_URL = "http://localhost:8010/v1"

def test_ingestion(file_path: str):
    path = Path(file_path)
    if not path.exists():
        print(f"❌ File not found: {file_path}")
        return

    print(f"\n📄 Uploading {path.name}...")
    
    # 1. Upload
    try:
        with open(path, "rb") as f:
            files = {"file": f}
            response = requests.post(f"{API_URL}/process_document", files=files)
            
        if response.status_code != 202:
            print(f"❌ Upload failed: {response.text}")
            return
            
        data = response.json()
        job_id = data["job_id"]
        print(f"✅ Job submitted! ID: {job_id}")
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to API. Is the server running? (python src/api/server.py)")
        return

    # 2. Poll Status
    print("⏳ Polling for status...")
    start_time = time.time()
    while True:
        try:
            status_resp = requests.get(f"{API_URL}/jobs/{job_id}")
            if status_resp.status_code != 200:
                print(f"❌ Failed to get status: {status_resp.text}")
                break
                
            job_data = status_resp.json()
            status = job_data["status"]
            print(f"   Status: {status}")
            
            if status == "COMPLETED":
                print("✅ Processing Completed!")
                print("   Result:", json.dumps(job_data.get("meta", {}).get("result"), indent=2))
                break
                
            if status == "FAILED":
                print("❌ Processing Failed!")
                print("   Error:", job_data.get("meta", {}).get("error"))
                break
                
            if time.time() - start_time > 60:
                print("⚠️ Timeout waiting for completion.")
                break
                
            time.sleep(2)
            
        except KeyboardInterrupt:
            break

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_ingestion_async.py <path_to_document_or_dir>")
        print("Example: python scripts/test_ingestion_async.py data/samples/invoice.pdf")
        
        # Look for default test dir
        test_dir = Path("data/samples")
        if test_dir.exists():
            print(f"\nDefaulting to files in {test_dir}...")
            for f in test_dir.glob("*"):
                 if f.is_file():
                     test_ingestion(str(f))
        return

    target = Path(sys.argv[1])
    
    if target.is_dir():
        for f in target.glob("*"):
            if f.is_file():
                test_ingestion(str(f))
    else:
        test_ingestion(str(target))

if __name__ == "__main__":
    main()
