from app import create_app, db
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    insp = inspect(db.engine)
    print(f"Tables: {insp.get_table_names()}")
    print(f"Module Columns: {[c['name'] for c in insp.get_columns('modules')]}")
    print(f"Page Columns: {[c['name'] for c in insp.get_columns('pages')]}")
