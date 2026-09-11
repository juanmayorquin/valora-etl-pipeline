"""Los scripts de src/ son standalone (no hay paquete): se agregan al path para que los
tests los importen como módulos."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

FIXTURES = Path(__file__).resolve().parent / "fixtures"
