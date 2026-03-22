# This file is kept as a compatibility shim.
# The primary entrypoint has moved to pump_architect/app.py.
#
# Run the app with:
#   streamlit run pump_architect/app.py
#
# If you accidentally run this file, it will redirect you automatically.

import sys
import os

# Allow `streamlit run pump_app.py` to still work by importing the new entrypoint
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

# Import the new app module so Streamlit picks up its page configuration
import pump_architect.app  # noqa: F401, E402