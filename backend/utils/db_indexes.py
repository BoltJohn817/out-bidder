"""Database index creation utilities for performance optimization."""
from extensions import db


def create_indexes():
    """
    Create database indexes for optimal query performance.
    Should be called once during application startup or migration.
    """
    # Users collection indexes
    users_collection = db["users"]
    users_collection.create_index("user_id", unique=True)
    users_collection.create_index("created_at")

    # Profiles collection indexes
    profiles_collection = db["profiles"]
    profiles_collection.create_index("owner_user_id")
    profiles_collection.create_index([("owner_user_id", 1), ("_id", 1)])  # Compound index for common queries
    profiles_collection.create_index("created_at")

    # Bids collection indexes
    bids_collection = db["bids"]
    bids_collection.create_index("owner_user_id")
    bids_collection.create_index([("owner_user_id", 1), ("created_at", -1)])  # Compound index for sorted queries
    bids_collection.create_index("profile_id")
    bids_collection.create_index("status")

    # Applications collection indexes
    applications_collection = db["applications"]
    applications_collection.create_index("owner_user_id")
    applications_collection.create_index([("owner_user_id", 1), ("profile_id", 1)])
    applications_collection.create_index(
        [
            ("owner_user_id", 1),
            ("profile_id", 1),
            ("spreadsheet_id", 1),
            ("sheet_id", 1),
        ]
    )  # Compound index for sheet queries
    applications_collection.create_index([("owner_user_id", 1), ("profile_id", 1), ("row_index", 1)])
    applications_collection.create_index("updated_at")

    # Job statuses collection indexes
    job_statuses_collection = db["job_statuses"]
    job_statuses_collection.create_index("job_id", unique=True)
    job_statuses_collection.create_index([("owner_user_id", 1), ("profile_id", 1)])
    job_statuses_collection.create_index("created_at")
    job_statuses_collection.create_index("updated_at")

    print("Database indexes created successfully")


if __name__ == "__main__":
    create_indexes()

