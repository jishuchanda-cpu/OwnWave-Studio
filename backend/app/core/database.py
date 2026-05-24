from sqlmodel import SQLModel, create_engine, Session
from app.core.config import settings

# SQLite connection args for multi-threaded FastAPI environments
connect_args = {"check_same_thread": False}
engine = create_engine(settings.DATABASE_URL, echo=False, connect_args=connect_args)

def init_db():
    # Import models here to register them with SQLModel
    from app.models.base import Project, Scene
    SQLModel.metadata.create_all(engine)
    
    # Safe auto-migration check for newly added columns
    import sqlite3
    from app.core.config import settings
    
    db_path = settings.STORAGE_DIR / "creator.db"
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Check projects table columns
            cursor.execute("PRAGMA table_info(projects)")
            project_columns = [row[1] for row in cursor.fetchall()]
            
            project_migrations = [
                ("duration_target", "TEXT DEFAULT '30s'"),
                ("voice_option", "TEXT DEFAULT 'english_female'"),
                ("current_stage", "TEXT DEFAULT 'ingest'"),
                ("stage_approved", "INTEGER DEFAULT 0"),
                ("stage_metadata", "TEXT DEFAULT '{}'")
            ]
            for col_name, col_type in project_migrations:
                if col_name not in project_columns:
                    print(f"[Migration] Adding column '{col_name}' to projects table")
                    cursor.execute(f"ALTER TABLE projects ADD COLUMN {col_name} {col_type}")
            
            # Check scenes table columns
            cursor.execute("PRAGMA table_info(scenes)")
            scene_columns = [row[1] for row in cursor.fetchall()]
            
            scene_migrations = [
                ("image_path_1", "TEXT"),
                ("image_path_2", "TEXT"),
                ("selected_image_index", "INTEGER DEFAULT 0"),
                ("transition_style", "TEXT DEFAULT 'fade'"),
                ("scene_duration", "REAL")
            ]
            for col_name, col_type in scene_migrations:
                if col_name not in scene_columns:
                    print(f"[Migration] Adding column '{col_name}' to scenes table")
                    cursor.execute(f"ALTER TABLE scenes ADD COLUMN {col_name} {col_type}")
            
            conn.commit()
            conn.close()
            print("[Migration] SQLite table schema checks complete.")
        except Exception as e:
            print(f"[Migration Error] Failed to complete schema checks: {e}")

def get_db():
    with Session(engine) as session:
        yield session

