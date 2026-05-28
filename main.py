from fastapi import FastAPI, Depends, HTTPException, Request, Form, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from typing import Optional
import json, os

from models import (
    get_db, Base, engine,
    Usuario, Permissao, Cliente, Equipamento, OrdemServico, PecaOS, Contador
)

# ─── Config ────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "servicedesk-secret-2024-mude-em-producao")
ALGORITHM  = "HS256"
TOKEN_EXP  = 60 * 8   # 8 horas

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ServiceDesk OS")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ─── Auth helpers ───────────────────────────────
def criar_token(data: dict):
    exp = datetime.utcnow() + timedelta(minutes=TOKEN_EXP)
    return jwt.encode({**data, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


def usuario_atual(request: Request, db: Session = Depends(get_db)) -> Optional[Usuario]:
    token = request.cookies.get("token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = payload.get("sub")
        return db.query(Usuario).filter_by(id=int(uid), ativo=True).first()
    except (JWTError, Exception):
        return None


def requer_login(request: Request, db: Session = Depends(get_db)) -> Usuario:
    u = usuario_atual(request, db)
    if not u:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return u


def permissoes_perfil(perfil: str, db: Session) -> dict:
    rows = db.query(Permissao).filter_by(perfil=perfil).all()
    return {r.chave: r.valor for r in rows}


def pode(perfil: str, chave: str, db: Session) -> bool:
    p = db.query(Permissao).filter_by(perfil=perfil, chave=chave).first()
    return bool(p and p.valor)


def proximo_numero_os(db: Session) -> str:
    c = db.query(Contador).filter_by(chave="os").first()
    if not c:
        from models import Contador as C
        c = C(chave="os", valor=1000)
        db.add(c)
    c.valor += 1
    db.commit()
    return f"OS-{c.valor}"


# ─── Páginas ────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def raiz(request: Request, db: Session = Depends(get_db)):
    u = usuario_atual(request, db)
    if u:
        return RedirectResponse("/dashboard")
    return RedirectResponse("/login")


@app.get("/login", response_class=HTMLResponse)
def pg_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "erro": ""})


@app.post("/login")
def fazer_login(request: Request, login: str = Form(...), senha: str = Form(...),
                db: Session = Depends(get_db)):
    u = db.query(Usuario).filter_by(login=login, ativo=True).first()
    if not u or not pwd_ctx.verify(senha, u.senha):
        return templates.TemplateResponse("login.html",
            {"request": request, "erro": "Usuário ou senha incorretos."})
    token = criar_token({"sub": str(u.id), "perfil": u.perfil})
    resp = RedirectResponse("/dashboard", status_code=303)
    resp.set_cookie("token", token, httponly=True, max_age=TOKEN_EXP * 60)
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("token")
    return resp


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if u.perfil == "Cliente":
        return RedirectResponse("/portal")
    perms = permissoes_perfil(u.perfil, db)
    stats = {
        "clientes":    db.query(Cliente).count(),
        "equipamentos": db.query(Equipamento).count(),
        "os_abertas":  db.query(OrdemServico).filter_by(status="Aberta").count(),
        "os_andamento": db.query(OrdemServico).filter_by(status="Em andamento").count(),
        "os_concluidas": db.query(OrdemServico).filter_by(status="Concluída").count(),
        "faturamento": db.query(OrdemServico).filter_by(status="Concluída").all(),
        "portal_abertas": db.query(OrdemServico).filter_by(origem="portal", status="Aberta").count(),
    }
    fat = sum(o.total for o in stats["faturamento"])
    ultimas = db.query(OrdemServico).order_by(OrdemServico.id.desc()).limit(5).all()
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "usuario": u, "perms": perms,
        "stats": stats, "faturamento": fat, "ultimas": ultimas,
    })


# ─── CLIENTES ───────────────────────────────────

@app.get("/clientes", response_class=HTMLResponse)
def pg_clientes(request: Request, q: str = "", tipo: str = "", db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if not pode(u.perfil, "verClientes", db):
        raise HTTPException(403)
    perms = permissoes_perfil(u.perfil, db)
    query = db.query(Cliente)
    if tipo:
        query = query.filter_by(tipo=tipo)
    if q:
        query = query.filter(Cliente.nome.ilike(f"%{q}%") |
                             Cliente.doc.ilike(f"%{q}%") |
                             Cliente.cidade.ilike(f"%{q}%") |
                             Cliente.email.ilike(f"%{q}%"))
    clientes = query.order_by(Cliente.nome).all()
    return templates.TemplateResponse("clientes.html", {
        "request": request, "usuario": u, "perms": perms,
        "clientes": clientes, "q": q, "tipo": tipo,
    })


@app.post("/clientes/novo")
def novo_cliente(request: Request,
    tipo: str = Form(...), nome: str = Form(...),
    doc: str = Form(""), tel: str = Form(""), email: str = Form(""),
    ie: str = Form(""), contato: str = Form(""),
    cep: str = Form(""), cidade: str = Form(""), estado: str = Form(""),
    bairro: str = Form(""), endereco: str = Form(""), obs: str = Form(""),
    db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if not pode(u.perfil, "editarClientes", db):
        raise HTTPException(403)
    db.add(Cliente(tipo=tipo, nome=nome, doc=doc, tel=tel, email=email,
                   ie=ie, contato=contato, cep=cep, cidade=cidade,
                   estado=estado, bairro=bairro, endereco=endereco, obs=obs))
    db.commit()
    return RedirectResponse("/clientes", status_code=303)


@app.post("/clientes/{cid}/excluir")
def excluir_cliente(cid: int, request: Request, db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if not pode(u.perfil, "editarClientes", db):
        raise HTTPException(403)
    c = db.query(Cliente).get(cid)
    if c:
        db.delete(c)
        db.commit()
    return RedirectResponse("/clientes", status_code=303)


# ─── EQUIPAMENTOS ───────────────────────────────

@app.get("/equipamentos", response_class=HTMLResponse)
def pg_equipamentos(request: Request, q: str = "", cliente_id: str = "",
                    db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if not pode(u.perfil, "verEquips", db):
        raise HTTPException(403)
    perms = permissoes_perfil(u.perfil, db)
    query = db.query(Equipamento)
    if cliente_id:
        query = query.filter_by(cliente_id=int(cliente_id))
    if q:
        query = query.filter(Equipamento.descricao.ilike(f"%{q}%") |
                             Equipamento.marca.ilike(f"%{q}%") |
                             Equipamento.modelo.ilike(f"%{q}%") |
                             Equipamento.serie.ilike(f"%{q}%"))
    equips   = query.order_by(Equipamento.descricao).all()
    clientes = db.query(Cliente).order_by(Cliente.nome).all()
    return templates.TemplateResponse("equipamentos.html", {
        "request": request, "usuario": u, "perms": perms,
        "equips": equips, "clientes": clientes,
        "q": q, "cliente_id": cliente_id,
    })


@app.post("/equipamentos/novo")
def novo_equip(request: Request,
    descricao: str = Form(...), marca: str = Form(""), modelo: str = Form(""),
    serie: str = Form(""), tag: str = Form(""), obs: str = Form(""),
    cliente_id: str = Form(""), db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if not pode(u.perfil, "editarEquips", db):
        raise HTTPException(403)
    db.add(Equipamento(descricao=descricao, marca=marca, modelo=modelo,
                       serie=serie, tag=tag, obs=obs,
                       cliente_id=int(cliente_id) if cliente_id else None))
    db.commit()
    return RedirectResponse("/equipamentos", status_code=303)


@app.post("/equipamentos/{eid}/excluir")
def excluir_equip(eid: int, request: Request, db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if not pode(u.perfil, "editarEquips", db):
        raise HTTPException(403)
    e = db.query(Equipamento).get(eid)
    if e:
        db.delete(e)
        db.commit()
    return RedirectResponse("/equipamentos", status_code=303)


# ─── ORDENS DE SERVIÇO ──────────────────────────

@app.get("/ordens", response_class=HTMLResponse)
def pg_ordens(request: Request, q: str = "", status: str = "",
              prioridade: str = "", cliente_id: str = "",
              db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if not pode(u.perfil, "verOS", db):
        raise HTTPException(403)
    perms = permissoes_perfil(u.perfil, db)
    query = db.query(OrdemServico)
    if status:
        query = query.filter_by(status=status)
    if prioridade:
        query = query.filter_by(prioridade=prioridade)
    if cliente_id:
        query = query.filter_by(cliente_id=int(cliente_id))
    if q:
        query = query.filter(OrdemServico.numero.ilike(f"%{q}%") |
                             OrdemServico.tecnico.ilike(f"%{q}%") |
                             OrdemServico.problema.ilike(f"%{q}%"))
    ordens   = query.order_by(OrdemServico.id.desc()).all()
    clientes = db.query(Cliente).order_by(Cliente.nome).all()
    return templates.TemplateResponse("ordens.html", {
        "request": request, "usuario": u, "perms": perms,
        "ordens": ordens, "clientes": clientes,
        "q": q, "status": status, "prioridade": prioridade, "cliente_id": cliente_id,
    })


@app.get("/ordens/nova", response_class=HTMLResponse)
def pg_nova_os(request: Request, db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if not pode(u.perfil, "editarOS", db):
        raise HTTPException(403)
    perms    = permissoes_perfil(u.perfil, db)
    clientes = db.query(Cliente).order_by(Cliente.nome).all()
    equips   = db.query(Equipamento).order_by(Equipamento.descricao).all()
    return templates.TemplateResponse("os_form.html", {
        "request": request, "usuario": u, "perms": perms,
        "clientes": clientes, "equips": equips, "os": None,
    })


@app.get("/ordens/{oid}/editar", response_class=HTMLResponse)
def pg_editar_os(oid: int, request: Request, db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if not pode(u.perfil, "editarOS", db):
        raise HTTPException(403)
    perms    = permissoes_perfil(u.perfil, db)
    os_obj   = db.query(OrdemServico).get(oid)
    clientes = db.query(Cliente).order_by(Cliente.nome).all()
    equips   = db.query(Equipamento).order_by(Equipamento.descricao).all()
    return templates.TemplateResponse("os_form.html", {
        "request": request, "usuario": u, "perms": perms,
        "clientes": clientes, "equips": equips, "os": os_obj,
    })


@app.post("/ordens/salvar")
def salvar_os(request: Request,
    os_id: str = Form(""),
    cliente_id: str = Form(...), equipamento_id: str = Form(""),
    tipo: str = Form(""), prioridade: str = Form("Normal"),
    tecnico: str = Form(""), prazo: str = Form(""),
    problema: str = Form(""), laudo: str = Form(""),
    status: str = Form("Aberta"), valor_mo: str = Form("0"),
    pecas_json: str = Form("[]"),
    db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if not pode(u.perfil, "editarOS", db):
        raise HTTPException(403)

    pecas_data = json.loads(pecas_json)
    total_pecas = sum(float(p.get("qtd", 0)) * float(p.get("preco", 0)) for p in pecas_data)
    mo   = float(valor_mo) if valor_mo else 0.0
    total = mo + total_pecas

    if os_id:
        os_obj = db.query(OrdemServico).get(int(os_id))
        if os_obj:
            os_obj.cliente_id    = int(cliente_id)
            os_obj.equipamento_id = int(equipamento_id) if equipamento_id else None
            os_obj.tipo          = tipo
            os_obj.prioridade    = prioridade
            os_obj.tecnico       = tecnico
            os_obj.prazo         = prazo
            os_obj.problema      = problema
            os_obj.laudo         = laudo
            os_obj.status        = status
            os_obj.valor_mo      = mo
            os_obj.total_pecas   = total_pecas
            os_obj.total         = total
            # Atualiza peças
            for p in os_obj.pecas:
                db.delete(p)
            db.flush()
    else:
        os_obj = OrdemServico(
            numero       = proximo_numero_os(db),
            cliente_id   = int(cliente_id),
            equipamento_id = int(equipamento_id) if equipamento_id else None,
            tipo=tipo, prioridade=prioridade, tecnico=tecnico, prazo=prazo,
            problema=problema, laudo=laudo, status=status,
            valor_mo=mo, total_pecas=total_pecas, total=total,
            origem="interno",
        )
        db.add(os_obj)
        db.flush()

    for p in pecas_data:
        qtd   = float(p.get("qtd", 0))
        preco = float(p.get("preco", 0))
        db.add(PecaOS(ordem_id=os_obj.id, descricao=p.get("desc",""),
                      qtd=qtd, preco=preco, subtotal=qtd * preco))
    db.commit()
    return RedirectResponse("/ordens", status_code=303)


@app.post("/ordens/{oid}/status")
def mudar_status(oid: int, request: Request,
                 status: str = Form(...), db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if not pode(u.perfil, "editarOS", db):
        raise HTTPException(403)
    os_obj = db.query(OrdemServico).get(oid)
    if os_obj:
        os_obj.status = status
        db.commit()
    return RedirectResponse("/ordens", status_code=303)


@app.post("/ordens/{oid}/excluir")
def excluir_os(oid: int, request: Request, db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if not pode(u.perfil, "editarOS", db):
        raise HTTPException(403)
    os_obj = db.query(OrdemServico).get(oid)
    if os_obj:
        db.delete(os_obj)
        db.commit()
    return RedirectResponse("/ordens", status_code=303)


@app.get("/ordens/{oid}/imprimir", response_class=HTMLResponse)
def imprimir_os(oid: int, request: Request, db: Session = Depends(get_db)):
    u = requer_login(request, db)
    os_obj = db.query(OrdemServico).get(oid)
    if not os_obj:
        raise HTTPException(404)
    return templates.TemplateResponse("os_print.html", {
        "request": request, "usuario": u, "os": os_obj,
        "cliente": os_obj.cliente,
        "equipamento": os_obj.equipamento,
        "pecas": os_obj.pecas,
    })


# ─── HISTÓRICO ──────────────────────────────────

@app.get("/historico", response_class=HTMLResponse)
def pg_historico(request: Request, cliente_id: str = "", db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if not pode(u.perfil, "verHistorico", db):
        raise HTTPException(403)
    perms    = permissoes_perfil(u.perfil, db)
    clientes = db.query(Cliente).order_by(Cliente.nome).all()
    ordens   = []
    cliente  = None
    stats    = {}
    if cliente_id:
        cliente = db.query(Cliente).get(int(cliente_id))
        ordens  = db.query(OrdemServico).filter_by(
            client_id=int(cliente_id)).order_by(OrdemServico.id.desc()).all()
        # corrige nome do campo
        ordens = db.query(OrdemServico).filter(
            OrdemServico.cliente_id == int(cliente_id)
        ).order_by(OrdemServico.id.desc()).all()
        stats = {
            "total":      len(ordens),
            "concluidas": sum(1 for o in ordens if o.status == "Concluída"),
            "abertas":    sum(1 for o in ordens if o.status in ["Aberta","Em andamento"]),
            "faturamento": sum(o.total for o in ordens),
        }
    return templates.TemplateResponse("historico.html", {
        "request": request, "usuario": u, "perms": perms,
        "clientes": clientes, "ordens": ordens,
        "cliente": cliente, "stats": stats,
        "cliente_id": cliente_id,
    })


# ─── PORTAL DO CLIENTE ──────────────────────────

@app.get("/portal", response_class=HTMLResponse)
def pg_portal(request: Request, db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if not pode(u.perfil, "verPortal", db):
        raise HTTPException(403)
    cliente = None
    equips  = []
    ordens  = []
    if u.cliente_id:
        cliente = db.query(Cliente).get(u.cliente_id)
        if cliente:
            equips = db.query(Equipamento).filter_by(cliente_id=cliente.id).all()
            ordens = db.query(OrdemServico).filter_by(
                cliente_id=cliente.id).order_by(OrdemServico.id.desc()).all()
    return templates.TemplateResponse("portal.html", {
        "request": request, "usuario": u,
        "cliente": cliente, "equips": equips, "ordens": ordens,
    })


@app.post("/portal/chamado")
def abrir_chamado(request: Request,
    equipamento_id: str = Form(""), tipo: str = Form(""),
    problema: str = Form(...), prioridade: str = Form("Normal"),
    db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if not pode(u.perfil, "verPortal", db):
        raise HTTPException(403)
    if not u.cliente_id:
        raise HTTPException(400, "Usuário sem cliente vinculado")
    db.add(OrdemServico(
        numero       = proximo_numero_os(db),
        cliente_id   = u.cliente_id,
        equipamento_id = int(equipamento_id) if equipamento_id else None,
        tipo=tipo, prioridade=prioridade,
        problema=problema, status="Aberta", origem="portal",
    ))
    db.commit()
    return RedirectResponse("/portal", status_code=303)


# ─── USUÁRIOS ───────────────────────────────────

@app.get("/usuarios", response_class=HTMLResponse)
def pg_usuarios(request: Request, db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if not pode(u.perfil, "verUsuarios", db):
        raise HTTPException(403)
    perms    = permissoes_perfil(u.perfil, db)
    usuarios = db.query(Usuario).order_by(Usuario.nome).all()
    clientes = db.query(Cliente).order_by(Cliente.nome).all()
    perms_db = {}
    for perfil in ["Administrador", "Técnico", "Cliente"]:
        perms_db[perfil] = permissoes_perfil(perfil, db)
    return templates.TemplateResponse("usuarios.html", {
        "request": request, "usuario": u, "perms": perms,
        "usuarios": usuarios, "clientes": clientes,
        "perms_perfis": perms_db,
        "perms_labels": [
            ("verClientes","Ver clientes"),("editarClientes","Cadastrar/editar clientes"),
            ("verEquips","Ver equipamentos"),("editarEquips","Cadastrar/editar equipamentos"),
            ("verOS","Ver ordens de serviço"),("editarOS","Criar/editar OS"),
            ("verHistorico","Ver histórico"),
            ("verUsuarios","Ver usuários"),("editarUsuarios","Gerenciar usuários"),
            ("verPortal","Portal do cliente"),
        ],
    })


@app.post("/usuarios/novo")
def novo_usuario(request: Request,
    nome: str = Form(...), login: str = Form(...),
    senha: str = Form(...), perfil: str = Form(...),
    cliente_id: str = Form(""), db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if not pode(u.perfil, "editarUsuarios", db):
        raise HTTPException(403)
    if db.query(Usuario).filter_by(login=login).first():
        raise HTTPException(400, "Login já em uso")
    db.add(Usuario(
        nome=nome, login=login, senha=pwd_ctx.hash(senha),
        perfil=perfil, ativo=True,
        cliente_id=int(cliente_id) if cliente_id else None,
    ))
    db.commit()
    return RedirectResponse("/usuarios", status_code=303)


@app.post("/usuarios/{uid}/toggle")
def toggle_usuario(uid: int, request: Request, db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if not pode(u.perfil, "editarUsuarios", db):
        raise HTTPException(403)
    tgt = db.query(Usuario).get(uid)
    if tgt and tgt.id != u.id:
        tgt.ativo = not tgt.ativo
        db.commit()
    return RedirectResponse("/usuarios", status_code=303)


@app.post("/usuarios/{uid}/excluir")
def excluir_usuario(uid: int, request: Request, db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if not pode(u.perfil, "editarUsuarios", db):
        raise HTTPException(403)
    tgt = db.query(Usuario).get(uid)
    if tgt and tgt.id != u.id and tgt.id != 1:
        db.delete(tgt)
        db.commit()
    return RedirectResponse("/usuarios", status_code=303)


@app.post("/usuarios/permissao")
async def salvar_permissao(request: Request, db: Session = Depends(get_db)):
    u = requer_login(request, db)
    if not pode(u.perfil, "editarUsuarios", db):
        raise HTTPException(403)
    data = await request.json()
    perfil = data.get("perfil")
    chave  = data.get("chave")
    valor  = data.get("valor")
    p = db.query(Permissao).filter_by(perfil=perfil, chave=chave).first()
    if p:
        p.valor = valor
    else:
        db.add(Permissao(perfil=perfil, chave=chave, valor=valor))
    db.commit()
    return JSONResponse({"ok": True})


# ─── API auxiliar para equipamentos por cliente ─

@app.get("/api/equips/{cliente_id}")
def api_equips(cliente_id: int, request: Request, db: Session = Depends(get_db)):
    requer_login(request, db)
    equips = db.query(Equipamento).filter_by(cliente_id=cliente_id).all()
    return [{"id": e.id, "label": f"{e.descricao}{' - '+e.marca if e.marca else ''}{' '+e.modelo if e.modelo else ''}"} for e in equips]
