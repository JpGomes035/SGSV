from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


class Usuario(db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nome_uvis = db.Column(db.String(100), nullable=False)
    regiao = db.Column(db.String(50))
    codigo_setor = db.Column(db.String(10))
    login = db.Column(db.String(50), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    tipo_usuario = db.Column(db.String(20), default='uvis')

    # Relacionamento: um usuário possui várias solicitações
    solicitacoes = db.relationship(
        'Solicitacao',
        backref='autor',
        lazy='select'
    )

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)


class Solicitacao(db.Model):
    __tablename__ = 'solicitacoes'

    id = db.Column(db.Integer, primary_key=True)

    # Dados da UVIS
    data_agendamento = db.Column(db.String(10), nullable=False)
    hora_agendamento = db.Column(db.String(5), nullable=False)
    endereco = db.Column(db.String(200), nullable=False)
    foco = db.Column(db.String(50), nullable=False)

    # Dados do admin
    coords = db.Column(db.String(100))        # Ex: "-23.5505, -46.6333"
    protocolo = db.Column(db.String(50))      # Ex: "BR-2025-0001"
    justificativa = db.Column(db.String(255))

    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='EM ANÁLISE')

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey('usuarios.id'),
        nullable=False
    )
