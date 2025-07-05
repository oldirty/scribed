"""Test package initialization."""

import pytest

# Import main package
import scribed
from scribed import ScribedDaemon, Config


class TestPackageInit:
    """Test package-level functionality."""
    
    def test_version_exists(self):
        """Test that version is defined."""
        assert hasattr(scribed, "__version__")
        assert isinstance(scribed.__version__, str)
        assert scribed.__version__ == "0.1.0"
    
    def test_author_exists(self):
        """Test that author is defined."""
        assert hasattr(scribed, "__author__")
        assert isinstance(scribed.__author__, str)
    
    def test_email_exists(self):
        """Test that email is defined."""
        assert hasattr(scribed, "__email__")
        assert isinstance(scribed.__email__, str)
    
    def test_exports(self):
        """Test that main classes are exported."""
        assert "ScribedDaemon" in scribed.__all__
        assert "Config" in scribed.__all__
    
    def test_imports(self):
        """Test that main classes can be imported."""
        assert ScribedDaemon is not None
        assert Config is not None
        
        # Test that they are the correct classes
        from scribed.daemon import ScribedDaemon as DaemonClass
        from scribed.config import Config as ConfigClass
        
        assert ScribedDaemon == DaemonClass
        assert Config == ConfigClass
