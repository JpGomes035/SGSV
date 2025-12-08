import os

class Config:
    # Gera uma chave secreta aleatória ou usa uma fixa
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'uma-chave-muito-secreta-dev'
    
    # Caminho do Banco de Dados
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'sgsv.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False