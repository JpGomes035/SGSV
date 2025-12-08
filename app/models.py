from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


# -------------------------------------------------------------
# USUÁRIO
# -------------------------------------------------------------
class Usuario(db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nome_uvis = db.Column(db.String(100), nullable=False)
    regiao = db.Column(db.String(50))
    codigo_setor = db.Column(db.String(10))

    login = db.Column(db.String(50), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)

    tipo_usuario = db.Column(db.String(20), default='uvis')

    # Relacionamento (1 usuário → várias solicitações)
    solicitacoes = db.relationship(
        "Solicitacao",
        backref="autor",
        lazy="select"
    )

    # Métodos utilitários
    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)


# -------------------------------------------------------------
# SOLICITAÇÃO DE VOO
# -------------------------------------------------------------
class Solicitacao(db.Model):
    __tablename__ = 'solicitacoes'

    id = db.Column(db.Integer, primary_key=True)

    # ----------------------
    # Dados da Solicitação
    # ----------------------
    data_agendamento = db.Column(db.String(10), nullable=False)
    hora_agendamento = db.Column(db.String(5), nullable=False)

    # Endereço (ViaCEP + preenchimento manual)
    cep = db.Column(db.String(9), nullable=False)
    logradouro = db.Column(db.String(150), nullable=False)
    bairro = db.Column(db.String(100), nullable=False)
    cidade = db.Column(db.String(100), nullable=False)
    uf = db.Column(db.String(2), nullable=False)

    numero = db.Column(db.String(20))
    complemento = db.Column(db.String(100))

    foco = db.Column(db.String(50), nullable=False)

    # ----------------------
    # Dados preenchidos pelo Admin
    # ----------------------
    coords = db.Column(db.String(100))
    protocolo = db.Column(db.String(50))
    justificativa = db.Column(db.String(255))

    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="EM ANÁLISE")

    # Relacionamento com o usuário
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=False
    )
