"""Native Messaging entry point. Never prints request data or exception text."""
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sources.tooncn_native_session import main

if __name__=='__main__':main()
