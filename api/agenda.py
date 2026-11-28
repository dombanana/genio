"""GênIO · Agenda simples da loja (salões, barbearias, clínicas) — dentro da página da loja, sem telefonia.

/var/lib/genio/dados/agenda/<slug>.json   configuração (serviços, profissionais, horário), reservas e bloqueios

Decisões do dono (28/11/2026):
- a agenda fica no GênIO, no servidor, separada do Fala Aí (que pode se ligar a ela depois);
- os horários são por profissional: o lojista cadastra os profissionais e o cliente escolhe com quem (ou "qualquer um");
- o cliente da loja informa nome e WhatsApp para agendar; não precisa de conta. A página avisa que esses dados ficam com a loja.
Regras:
- dois clientes nunca ficam com o mesmo horário do mesmo profissional (a reserva confere de novo com a trava fechada);
- nesta versão o sistema não envia lembrete; o cliente põe o horário na agenda do próprio celular;
- reservas com mais de 90 dias saem do arquivo (não guardar dado pessoal sem necessidade).
"""
import datetime as dt, hashlib, os, re, secrets, threading
import dados as DADOS

try:
    from zoneinfo import ZoneInfo
    FUSO = ZoneInfo("America/Sao_Paulo")
except Exception:   # servidor sem base de fusos: São Paulo é UTC-3 o ano todo
    FUSO = dt.timezone(dt.timedelta(hours=-3))

PASTA = os.path.join(DADOS.RAIZ_DADOS, "agenda")
PASSOS = (15, 20, 30, 60)
ATIVAS = ("marcado", "confirmado")
GUARDA_DIAS = 90
MAX_POR_APARELHO = 3
HORARIO_PADRAO = {"0": [["09:00", "18:00"]], "1": [["09:00", "18:00"]], "2": [["09:00", "18:00"]], "3": [["09:00", "18:00"]],
                  "4": [["09:00", "18:00"]], "5": [["09:00", "13:00"]], "6": []}   # 0 = segunda … 6 = domingo
_lock = threading.Lock()
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DIA = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def _agora():
    return dt.datetime.now(FUSO).replace(tzinfo=None)

def _h(tok):
    return hashlib.sha256(("ag|" + str(tok)).encode()).hexdigest()[:32]

def _arq(slug):
    return os.path.join(PASTA, DADOS.valida_slug(slug) + ".json")

def ler(slug):
    e = DADOS._ler_json(_arq(slug))
    if not e:
        e = {"slug": slug, "config": {"ativo": False, "passo": 30, "dias_frente": 30, "antecedencia_min": 60, "servicos": [], "profissionais": [],
                                      "horario": {k: [list(j) for j in v] for k, v in HORARIO_PADRAO.items()}}, "reservas": [], "bloqueios": []}
    return e

def _gravar(slug, e):
    corte = (_agora().date() - dt.timedelta(days=GUARDA_DIAS)).isoformat()
    e["reservas"] = [r for r in e.get("reservas", []) if r.get("dia", "") >= corte]
    e["bloqueios"] = [b for b in e.get("bloqueios", []) if b.get("dia", "") >= corte]
    os.makedirs(PASTA, exist_ok=True)
    DADOS._escrever_json(_arq(slug), e)

def _min(h):
    return int(h[:2]) * 60 + int(h[3:5])

def _hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"

def _serv(e, sid):
    return next((s for s in e["config"].get("servicos", []) if s["id"] == sid), None)

def _prof(e, pid):
    return next((p for p in e["config"].get("profissionais", []) if p["id"] == pid), None)

def _faz(p, sid):
    return not p.get("servicos") or sid in p["servicos"]

def _pronta(e):
    c = e["config"]
    return bool(c.get("ativo") and c.get("servicos") and c.get("profissionais"))

def _ocupado(e, pid, dia, fora=None):
    o = [(_min(r["ini"]), _min(r["fim"])) for r in e.get("reservas", []) if r["prof"] == pid and r["dia"] == dia and r["estado"] in ATIVAS and r["id"] != fora]
    o += [(_min(b["ini"]), _min(b["fim"])) for b in e.get("bloqueios", []) if b["dia"] == dia and b.get("prof") in (pid, "todos")]
    return o

def _livres_prof(e, pid, dur, dia, fora=None, sem_antecedencia=False):
    c = e["config"]; d = dt.date.fromisoformat(dia); agora = _agora()
    if d < agora.date():
        return []
    piso = 0
    if d == agora.date():
        piso = agora.hour * 60 + agora.minute + (0 if sem_antecedencia else int(c.get("antecedencia_min") or 0))
    occ = _ocupado(e, pid, dia, fora); passo = int(c.get("passo") or 30); out = []
    for ini, fim in (c.get("horario") or {}).get(str(d.weekday()), []):
        t = _min(ini)
        while t + dur <= _min(fim):
            if t >= piso and not any(t < b and a < t + dur for a, b in occ):
                out.append(t)
            t += passo
    return out

def livres(e, sid, pid, dia, fora=None, sem_antecedencia=False):
    """horários livres do dia para o serviço; pid vazio = qualquer profissional que faça o serviço (devolve quem está livre em cada horário)"""
    s = _serv(e, sid)
    if not s or not DIA.match(dia or ""):
        return []
    profs = [p for p in e["config"].get("profissionais", []) if _faz(p, sid) and (not pid or p["id"] == pid)]
    por_hora = {}
    for p in profs:
        for t in _livres_prof(e, p["id"], int(s["min"]), dia, fora, sem_antecedencia):
            por_hora.setdefault(t, p["id"])
    return [{"h": _hhmm(t), "p": por_hora[t]} for t in sorted(por_hora)]

def dias_livres(e, sid, pid):
    hoje = _agora().date(); n = min(60, max(1, int(e["config"].get("dias_frente") or 30))); out = []
    for i in range(n + 1):
        d = (hoje + dt.timedelta(days=i)).isoformat()
        k = len(livres(e, sid, pid, d))
        if k:
            out.append({"d": d, "n": k})
    return out

def _pub_reserva(r):
    return {k: r.get(k) for k in ("id", "serv_nome", "min", "preco", "prof_nome", "dia", "ini", "fim", "estado")}

# ---------- cliente da loja (página pública pelo QR) ----------
def publica(slug, tok):
    e = ler(slug)
    if not _pronta(e):
        return {"ativo": False}
    c = e["config"]; hoje = _agora().date().isoformat(); ap = _h(tok) if tok else None
    return {"ativo": True, "servicos": [{"id": s["id"], "nome": s["nome"], "min": s["min"], "preco": s.get("preco") or ""} for s in c["servicos"]],
            "profissionais": [{"id": p["id"], "nome": p["nome"], "servicos": p.get("servicos") or []} for p in c["profissionais"]],
            "minhas": sorted([_pub_reserva(r) for r in e["reservas"] if ap and r.get("ap") == ap and r["dia"] >= hoje and r["estado"] in ATIVAS], key=lambda r: (r["dia"], r["ini"]))}

def horarios(slug, sid, pid, dia):
    e = ler(slug)
    if not _pronta(e):
        raise FileNotFoundError
    if not _serv(e, sid):
        raise ValueError("escolha o serviço")
    if pid and not _prof(e, pid):
        raise ValueError("profissional não encontrado")
    return {"horarios": livres(e, sid, pid, dia)} if dia else {"dias": dias_livres(e, sid, pid)}

def _nome(v):
    v = re.sub(r"\s+", " ", str(v or "")).strip()
    if not 2 <= len(v) <= 60:
        raise ValueError("diga o seu nome")
    return v

def _tel(v, obrigatorio=True):
    d = re.sub(r"\D", "", str(v or ""))
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    if not d and not obrigatorio:
        return ""
    if len(d) not in (10, 11):
        raise ValueError("informe o WhatsApp com DDD")
    return d

def _nova(e, sid, pid, dia, h, nome, tel, origem, ap=None, sem_antecedencia=False):
    s = _serv(e, sid)
    if not s:
        raise ValueError("escolha o serviço")
    if not DIA.match(dia or "") or not HHMM.match(h or ""):
        raise ValueError("escolha o dia e o horário")
    livre = next((x for x in livres(e, sid, pid, dia, sem_antecedencia=sem_antecedencia) if x["h"] == h), None)
    if not livre:
        raise ValueError("esse horário acabou de ser ocupado. Escolha outro.")
    p = _prof(e, livre["p"])
    r = {"id": secrets.token_hex(6), "serv": s["id"], "serv_nome": s["nome"], "min": int(s["min"]), "preco": s.get("preco") or "", "prof": p["id"], "prof_nome": p["nome"],
         "dia": dia, "ini": h, "fim": _hhmm(_min(h) + int(s["min"])), "nome": nome, "tel": tel, "estado": "marcado", "origem": origem,
         "criado": _agora().isoformat(timespec="seconds")}
    if ap:
        r["ap"] = ap
    e["reservas"].append(r)
    return r

def reservar(slug, tok, d):
    with _lock:
        e = ler(slug)
        if not _pronta(e):
            raise FileNotFoundError
        nome = _nome(d.get("nome")); tel = _tel(d.get("tel")); ap = _h(tok); hoje = _agora().date().isoformat()
        if sum(1 for r in e["reservas"] if r.get("ap") == ap and r["dia"] >= hoje and r["estado"] in ATIVAS) >= MAX_POR_APARELHO:
            raise ValueError(f"você já tem {MAX_POR_APARELHO} horários marcados aqui. Cancele um para marcar outro.")
        r = _nova(e, str(d.get("servico") or ""), str(d.get("profissional") or ""), str(d.get("dia") or ""), str(d.get("hora") or ""), nome, tel, "cliente", ap)
        _gravar(slug, e)
        return _pub_reserva(r)

def cancelar(slug, tok, rid):
    with _lock:
        e = ler(slug); ap = _h(tok)
        r = next((x for x in e["reservas"] if x["id"] == rid and x.get("ap") == ap), None)
        if not r:
            raise FileNotFoundError
        if r["estado"] in ATIVAS:
            r["estado"] = "cancelado"; r["cancelado_por"] = "cliente"; r["cancelado_em"] = _agora().isoformat(timespec="seconds")
            _gravar(slug, e)
        return _pub_reserva(r)

# ---------- lojista (painel) ----------
def painel(slug):
    e = ler(slug); hoje = _agora().date(); ontem = (hoje - dt.timedelta(days=1)).isoformat()
    rs = sorted([{k: r.get(k) for k in ("id", "serv", "serv_nome", "min", "preco", "prof", "prof_nome", "dia", "ini", "fim", "nome", "tel", "estado", "origem", "cancelado_por")}
                 for r in e["reservas"] if r["dia"] >= ontem], key=lambda r: (r["dia"], r["ini"]))
    return {"config": e["config"], "pronta": _pronta(e), "hoje": hoje.isoformat(), "reservas": rs,
            "bloqueios": sorted([b for b in e["bloqueios"] if b["dia"] >= hoje.isoformat()], key=lambda b: (b["dia"], b["ini"])),
            "indicadores": {"hoje": sum(1 for r in rs if r["dia"] == hoje.isoformat() and r["estado"] in ATIVAS),
                            "proximos": sum(1 for r in rs if r["dia"] > hoje.isoformat() and r["estado"] in ATIVAS),
                            "a_confirmar": sum(1 for r in rs if r["dia"] >= hoje.isoformat() and r["estado"] == "marcado")}}

def _id(v, usados):
    v = str(v or "")
    if re.fullmatch(r"[a-z0-9]{4,12}", v) and v not in usados:
        return v
    while True:
        n = secrets.token_hex(3)
        if n not in usados:
            return n

def config_gravar(slug, d):
    with _lock:
        e = ler(slug); c = e["config"]; d = d if isinstance(d, dict) else {}
        if "servicos" in d:
            out = []; usados = set()
            for s in (d.get("servicos") or [])[:30]:
                nome = re.sub(r"\s+", " ", str(s.get("nome") or "")).strip()[:40]
                if not nome:
                    continue
                try:
                    m = int(s.get("min") or 30)
                except Exception:
                    m = 30
                sid = _id(s.get("id"), usados); usados.add(sid)
                out.append({"id": sid, "nome": nome, "min": max(10, min(480, m)), "preco": re.sub(r"[^\d,\.]", "", str(s.get("preco") or ""))[:10]})
            c["servicos"] = out
        if "profissionais" in d:
            out = []; usados = set(); sids = {s["id"] for s in c["servicos"]}
            for p in (d.get("profissionais") or [])[:12]:
                nome = re.sub(r"\s+", " ", str(p.get("nome") or "")).strip()[:30]
                if not nome:
                    continue
                pid = _id(p.get("id"), usados); usados.add(pid)
                out.append({"id": pid, "nome": nome, "servicos": [x for x in (p.get("servicos") or []) if x in sids]})
            c["profissionais"] = out
        if "horario" in d:
            hz = {}
            for k in "0123456":
                js = []
                for j in ((d.get("horario") or {}).get(k) or [])[:2]:
                    if isinstance(j, (list, tuple)) and len(j) == 2 and HHMM.match(str(j[0])) and HHMM.match(str(j[1])) and _min(j[0]) < _min(j[1]):
                        js.append([j[0], j[1]])
                hz[k] = sorted(js)
            c["horario"] = hz
        if "passo" in d and int(d.get("passo") or 0) in PASSOS:
            c["passo"] = int(d["passo"])
        if "antecedencia_min" in d:
            c["antecedencia_min"] = max(0, min(1440, int(d.get("antecedencia_min") or 0)))
        if "dias_frente" in d:
            c["dias_frente"] = max(1, min(60, int(d.get("dias_frente") or 30)))
        if "ativo" in d:
            c["ativo"] = bool(d.get("ativo"))
        _gravar(slug, e)
        return painel(slug)

def loja_reservar(slug, d, por):
    with _lock:
        e = ler(slug)
        r = _nova(e, str(d.get("servico") or ""), str(d.get("profissional") or ""), str(d.get("dia") or ""), str(d.get("hora") or ""),
                  _nome(d.get("nome")), _tel(d.get("tel"), obrigatorio=False), "loja", sem_antecedencia=True)
        r["por"] = por; r["estado"] = "confirmado"
        _gravar(slug, e)
        return r["id"]

def loja_marcar(slug, rid, acao, d=None):
    with _lock:
        e = ler(slug); r = next((x for x in e["reservas"] if x["id"] == rid), None)
        if not r:
            raise FileNotFoundError
        if acao == "confirmar":
            if r["estado"] == "marcado":
                r["estado"] = "confirmado"
        elif acao == "cancelar":
            if r["estado"] in ATIVAS:
                r["estado"] = "cancelado"; r["cancelado_por"] = "loja"; r["cancelado_em"] = _agora().isoformat(timespec="seconds")
        elif acao in ("feito", "faltou"):
            r["estado"] = acao
        elif acao == "remarcar":
            d = d or {}; dia = str(d.get("dia") or ""); h = str(d.get("hora") or ""); pid = str(d.get("profissional") or r["prof"])
            if r["estado"] not in ATIVAS:
                raise ValueError("só dá para remarcar um horário que ainda está marcado")
            if not DIA.match(dia) or not HHMM.match(h):
                raise ValueError("escolha o dia e o horário")
            livre = next((x for x in livres(e, r["serv"], pid, dia, fora=rid, sem_antecedencia=True) if x["h"] == h), None)
            if not livre:
                raise ValueError("esse horário não está livre")
            p = _prof(e, livre["p"])
            r.update({"dia": dia, "ini": h, "fim": _hhmm(_min(h) + int(r["min"])), "prof": p["id"], "prof_nome": p["nome"], "remarcado_em": _agora().isoformat(timespec="seconds")})
        else:
            raise ValueError("ação?")
        _gravar(slug, e)

def loja_horarios(slug, sid, pid, dia, fora=None):
    e = ler(slug)
    return {"horarios": livres(e, sid, pid, dia, fora=fora, sem_antecedencia=True)}

def bloquear(slug, d):
    with _lock:
        e = ler(slug); dia = str(d.get("dia") or ""); ini = str(d.get("ini") or ""); fim = str(d.get("fim") or ""); pid = str(d.get("profissional") or "todos")
        if not DIA.match(dia) or not HHMM.match(ini) or not HHMM.match(fim) or _min(ini) >= _min(fim):
            raise ValueError("informe o dia e o intervalo")
        if pid != "todos" and not _prof(e, pid):
            raise ValueError("profissional não encontrado")
        choque = [r for r in e["reservas"] if r["dia"] == dia and r["estado"] in ATIVAS and (pid == "todos" or r["prof"] == pid) and _min(r["ini"]) < _min(fim) and _min(ini) < _min(r["fim"])]
        if choque:
            raise ValueError(f"já há {len(choque)} horário(s) marcado(s) nesse intervalo ({', '.join(r['ini'] + ' ' + r['nome'] for r in choque[:3])}). Remarque ou cancele antes de fechar.")
        e["bloqueios"].append({"id": secrets.token_hex(5), "prof": pid, "dia": dia, "ini": ini, "fim": fim, "motivo": str(d.get("motivo") or "")[:60]})
        _gravar(slug, e)

def desbloquear(slug, bid):
    with _lock:
        e = ler(slug); n = len(e["bloqueios"])
        e["bloqueios"] = [b for b in e["bloqueios"] if b["id"] != bid]
        if len(e["bloqueios"]) == n:
            raise FileNotFoundError
        _gravar(slug, e)
