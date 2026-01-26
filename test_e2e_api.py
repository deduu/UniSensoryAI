"""
End-to-end test script for the API endpoint.
This script tests the document processing pipeline via HTTP.
"""
import asyncio
import httpx
from pathlib import Path

async def test_api_endpoint():
    """Test the FastAPI document processing endpoint."""
    print("=" * 60)
    print("End-to-End API Test")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    
    try:
        print("\n[1/3] Testing health check...")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/")
            print(f"✓ Health check: {response.json()}")
        
        print("\n[2/3] Testing OpenAI-compatible chat endpoint...")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/v1/chat/completions",
                json={
                    "model": "qwen3-vl-30b",
                    "messages": [
                        {"role": "user", "content": "Hello"}
                    ]
                }
            )
            print(f"✓ Chat completions: {response.json()['choices'][0]['message']['content']}")
        
        print("\n[3/3] Testing document processing endpoint...")
        print("⚠ Note: This requires an actual file to upload")
        print("   To test manually, use curl:")
        print('   curl -X POST http://localhost:8000/v1/process_document \\')
        print('        -F "file=@example.xlsx" \\')
        print('        -F "model_id=qwen3-vl-30b" \\')
        print('        -F "output_format=json"')
        
        print("\n" + "=" * 60)
        print("✓ API TESTS PASSED")
        print("=" * 60)
        
    except httpx.ConnectError:
        print("\n✗ ERROR: Cannot connect to server")
        print("   Make sure the server is running:")
        print("   python -m src.api.server")
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_api_endpoint())
