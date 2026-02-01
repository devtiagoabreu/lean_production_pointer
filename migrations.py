from app import app, db
from datetime import datetime

with app.app_context():
    # Criar todas as tabelas
    db.create_all()
    print("Tabelas criadas com sucesso!")