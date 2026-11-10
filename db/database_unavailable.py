# Lennart
# Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".

class DatabaseUnavailable(RuntimeError):
    # The database could not be opened (server down, wrong URL, bad password, unwritable file). The message
    # never contains the connection string, so it is safe to show to the user.
    pass
