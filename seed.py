"""
Popula o banco com usuários padrão e permissões iniciais.
Execute uma vez: python seed.py
"""
from models import Base, engine, SessionLocal, Usuario, Permissao, Contador
from passlib.context import CryptContext

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

PERFIS = ["Administrador", "Técnico", "Cliente"]

PERMS_DEFAULT = {
    "Administrador": {
        "verClientes": True, "editarClientes": True,
        "verEquips": True,   "editarEquips": True,
        "verOS": True,       "editarOS": True,
        "verHistorico": True,
        "verUsuarios": True, "editarUsuarios": True,
        "verPortal": False,
    },
    "Técnico": {
        "verClientes": True, "editarClientes": False,
        "verEquips": True,   "editarEquips": False,
        "verOS": True,       "editarOS": True,
        "verHistorico": True,
        "verUsuarios": False, "editarUsuarios": False,
        "verPortal": False,
    },
    "Cliente": {
        "verClientes": False, "editarClientes": False,
        "verEquips": False,   "editarEquips": False,
        "verOS": False,       "editarOS": False,
        "verHistorico": False,
        "verUsuarios": False, "editarUsuarios": False,
        "verPortal": True,
    },
}

USUARIOS_PADRAO = [
    {"nome": "Administrador", "login": "admin",    "senha": "admin123",  "perfil": "Administrador"},
    {"nome": "Técnico João",  "login": "tecnico1", "senha": "tec123",    "perfil": "Técnico"},
    {"nome": "Cliente Demo",  "login": "cliente1", "senha": "cli123",    "perfil": "Cliente"},
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Permissões
    if not db.query(Permissao).first():
        for perfil, perms in PERMS_DEFAULT.items():
            for chave, valor in perms.items():
                db.add(Permissao(perfil=perfil, chave=chave, valor=valor))
        print("✔ Permissões criadas")

    # Usuários
    if not db.query(Usuario).first():
        for u in USUARIOS_PADRAO:
            db.add(Usuario(
                nome=u["nome"], login=u["login"],
                senha=pwd.hash(u["senha"]), perfil=u["perfil"], ativo=True
            ))
        print("✔ Usuários padrão criados")

    # Contador de OS
    if not db.query(Contador).filter_by(chave="os").first():
        db.add(Contador(chave="os", valor=1000))
        print("✔ Contador OS criado")

    db.commit()
    db.close()
    print("✔ Banco inicializado com sucesso!")


if __name__ == "__main__":
    seed()
