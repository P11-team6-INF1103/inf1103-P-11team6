# Lennart

class DatabaseUnavailable(RuntimeError):
    # The database could not be opened (server down, wrong URL, bad password, unwritable file). The message
    # never contains the connection string, so it is safe to show to the user.
    pass
