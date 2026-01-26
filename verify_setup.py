"""
Verification script to test the basic setup and imports.
Run this to verify the core architecture is correctly implemented.
"""
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def verify_imports():
    """Verify all core imports work."""
    print("=" * 60)
    print("UniSensoryAI Setup Verification")
    print("=" * 60)
    
    try:
        print("\n[1/5] Testing core imports...")
        from src.core import (
            BaseVisionLanguageModel,
            BaseAgent,
            Document,
            DocumentType,
            ProcessingResult
        )
        print("✓ Core abstractions imported successfully")
        
        print("\n[2/5] Testing model loader imports...")
        from src.models import ModelLoader, HuggingFaceModel, DeepSeekModel, CloudAPIModel
        print("✓ Model loaders imported successfully")
        
        print("\n[3/5] Testing configuration loader...")
        from src.utils import ConfigLoader
        config_path = Path(__file__).parent / "configs" / "models.yaml"
        if config_path.exists():
            config = ConfigLoader.load_yaml(config_path)
            available_models = list(config.get("models", {}).keys())
            print(f"✓ Configuration loaded. Available models: {available_models}")
        else:
            print("⚠ configs/models.yaml not found")
        
        print("\n[4/5] Testing agent imports...")
        from src.agents.excel_agent import ExcelParserAgent
        print("✓ ExcelParserAgent imported successfully")
        
        print("\n[5/5] Verifying class hierarchy...")
        assert issubclass(HuggingFaceModel, BaseVisionLanguageModel)
        assert issubclass(DeepSeekModel, BaseVisionLanguageModel)
        assert issubclass(CloudAPIModel, BaseVisionLanguageModel)
        assert issubclass(ExcelParserAgent, BaseAgent)
        print("✓ Class hierarchy verified")
        
        print("\n" + "=" * 60)
        print("✓ ALL CHECKS PASSED")
        print("=" * 60)
        print("\nThe core architecture is correctly set up!")
        print("Next steps:")
        print("  1. Install dependencies: pip install -e .[dev]")
        print("  2. Run API server: python -m src.api.server")
        print("  3. Test endpoint: POST http://localhost:8000/v1/process_document")
        
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = verify_imports()
    sys.exit(0 if success else 1)
