# Copy this file to secrets.py and fill in the values for this machine.
# secrets.py is gitignored, so every machine keeps its own.

# Folder the backend is deployed into, e.g. the IIS site root
Deploy_Target = r"Path to the IIS folder hosting the backend"

# IIS app pool to recycle after a deploy. Recycling one needs an elevated shell; leave
# this as None to just touch web.config, which restarts the app without elevation
App_Pool = None
