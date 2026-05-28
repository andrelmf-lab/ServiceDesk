from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# SQLite para desenvolvimento — troque pela linha PostgreSQL para produção
DATABASE_URL = "sqlite:///./servicedesk.db"
# DATABASE_URL = "postgresql://user:password@localhost/servicedesk"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─────────────────────────────────────────────
class Usuario(Base):
    __tablename__ = "usuarios"
    id        = Column(Integer, primary_key=True, index=True)
    nome      = Column(String(120), nullable=False)
    login     = Column(String(60), unique=True, nullable=False)
    senha     = Column(String(200), nullable=False)   # bcrypt hash
    perfil    = Column(String(20), nullable=False)     # Administrador | Técnico | Cliente
    ativo     = Column(Boolean, default=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    cliente   = relationship("Cliente", foreign_keys=[cliente_id])


class Permissao(Base):
    __tablename__ = "permissoes"
    id        = Column(Integer, primary_key=True)
    perfil    = Column(String(20), nullable=False)
    chave     = Column(String(60), nullable=False)
    valor     = Column(Boolean, default=False)


class Cliente(Base):
    __tablename__ = "clientes"
    id        = Column(Integer, primary_key=True, index=True)
    tipo      = Column(String(2), nullable=False)      # PF | PJ
    nome      = Column(String(150), nullable=False)
    doc       = Column(String(20))
    tel       = Column(String(20))
    email     = Column(String(100))
    ie        = Column(String(30))
    contato   = Column(String(100))
    cep       = Column(String(10))
    cidade    = Column(String(80))
    estado    = Column(String(2))
    bairro    = Column(String(80))
    endereco  = Column(String(200))
    obs       = Column(Text)
    criado_em = Column(DateTime, default=datetime.utcnow)

    equipamentos = relationship("Equipamento", back_populates="cliente")
    ordens       = relationship("OrdemServico", back_populates="cliente")


class Equipamento(Base):
    __tablename__ = "equipamentos"
    id         = Column(Integer, primary_key=True, index=True)
    descricao  = Column(String(150), nullable=False)
    marca      = Column(String(80))
    modelo     = Column(String(80))
    serie      = Column(String(80))
    tag        = Column(String(60))
    obs        = Column(Text)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    criado_em  = Column(DateTime, default=datetime.utcnow)

    cliente = relationship("Cliente", back_populates="equipamentos")
    ordens  = relationship("OrdemServico", back_populates="equipamento")


class OrdemServico(Base):
    __tablename__ = "ordens_servico"
    id           = Column(Integer, primary_key=True, index=True)
    numero       = Column(String(20), unique=True, nullable=False)
    cliente_id   = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    equipamento_id = Column(Integer, ForeignKey("equipamentos.id"), nullable=True)
    tipo         = Column(String(60))
    prioridade   = Column(String(20), default="Normal")
    tecnico      = Column(String(100))
    prazo        = Column(String(20))
    problema     = Column(Text)
    laudo        = Column(Text)
    status       = Column(String(30), default="Aberta")
    valor_mo     = Column(Float, default=0.0)   # mão de obra
    total_pecas  = Column(Float, default=0.0)
    total        = Column(Float, default=0.0)
    origem       = Column(String(20), default="interno")  # interno | portal
    criado_em    = Column(DateTime, default=datetime.utcnow)

    cliente    = relationship("Cliente", back_populates="ordens")
    equipamento = relationship("Equipamento", back_populates="ordens")
    pecas      = relationship("PecaOS", back_populates="ordem", cascade="all, delete-orphan")


class PecaOS(Base):
    __tablename__ = "pecas_os"
    id        = Column(Integer, primary_key=True)
    ordem_id  = Column(Integer, ForeignKey("ordens_servico.id"), nullable=False)
    descricao = Column(String(200))
    qtd       = Column(Float, default=1)
    preco     = Column(Float, default=0.0)
    subtotal  = Column(Float, default=0.0)

    ordem = relationship("OrdemServico", back_populates="pecas")


# ─── Contador de OS ───────────────────────────
class Contador(Base):
    __tablename__ = "contadores"
    id    = Column(Integer, primary_key=True)
    chave = Column(String(30), unique=True)
    valor = Column(Integer, default=1000)
