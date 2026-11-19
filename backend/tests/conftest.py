import os

# Importing app.main builds the module-level app (what Vercel serves). Point it at a
# throwaway in-memory database for tests; each test still builds its own app.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["LOG_LEVEL"] = "WARNING"
