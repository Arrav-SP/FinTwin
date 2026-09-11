from backend.app.database import initialize_schema


if __name__ == "__main__":
    initialize_schema()
    print("Database schema initialized successfully.")

