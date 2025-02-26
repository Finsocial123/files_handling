"""
Test script to verify all required packages are installed correctly.
"""
import sys
import importlib.util

def check_import(package_name):
    """Check if a package can be imported and print its version."""
    try:
        spec = importlib.util.find_spec(package_name)
        if spec is None:
            print(f"❌ {package_name}: Not installed")
            return False
        
        module = importlib.import_module(package_name)
        version = getattr(module, '__version__', 'unknown')
        print(f"✅ {package_name}: {version}")
        return True
    except ImportError:
        print(f"❌ {package_name}: Import error")
        return False

def main():
    """Test all required imports."""
    packages = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "python_multipart",
        "aiofiles",
        "dotenv",
        "requests",
        "langchain",
        "openai",
        "pypdf",
        "docx2txt",
        "openpyxl"
    ]
    
    success = all(check_import(pkg) for pkg in packages)
    
    if success:
        print("\nAll imports successful! Environment is correctly set up.")
        sys.exit(0)
    else:
        print("\nSome imports failed. Please check your installation.")
        sys.exit(1)

if __name__ == "__main__":
    main()
