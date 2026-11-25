"""GênIO · leitura do cardápio por foto (para o Mostraí e a página da loja).

Recebe 1 a 4 fotos (JPEG já reduzido no aparelho) e devolve as categorias com os itens: nome, preço, complemento.
Nada é inventado: o que a leitura não tem certeza volta marcado como "incerto" e o preço fica vazio para conferir com o dono.
Provedores, na ordem: Claude (ANTHROPIC_KEY), Gemini (GEMINI_KEY), OpenAI (OPENAI_KEY) — o primeiro que responder.
Cada leitura fica registrada em /var/lib/genio/ia.log (provedor, modelo, fotos, tokens quando o provedor informa).
"""
import base64, json, os, re, time
from urllib import request as _rq

PROMPT = """Você recebe foto(s) do cardápio ou da tabela de preços de uma loja ({setor}).
Transcreva EXATAMENTE o que está escrito. Não invente item, preço nem descrição.
Responda só com JSON, neste formato:
{{"categorias":[{{"nome":"nome da seção como está no cardápio (ou 'Itens' se não houver)","itens":[{{"nome":"nome do item","preco":"só o número no formato 12,90 (vazio se não houver ou não der para ler)","desc":"complemento curto como está escrito: tamanho, peso, porção, ingredientes principais (até 40 letras; vazio se não houver)","apartir":false,"incerto":false}}]}}],"observacoes":"o que não deu para ler, em uma frase (vazio se tudo leu bem)"}}
Regras:
- "incerto": true quando o nome ou o preço estiver borrado, cortado ou duvidoso; nesse caso deixe o preço vazio.
- "apartir": true só quando o cardápio diz "a partir de".
- Item com vários tamanhos e preços (P/M/G, 300 ml/500 ml): um item por tamanho, com o tamanho no "desc".
- Mantenha a ordem do cardápio. Ignore telefone, endereço, redes sociais e textos de propaganda.
- Nomes com a grafia do cardápio, sem TUDO MAIÚSCULO (só a primeira letra maiúscula, salvo siglas)."""

def _limpa_json(txt):
    txt = (txt or "").strip()
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise ValueError("a leitura não devolveu uma lista")
    return json.loads(m.group(0))

def _preco(p):
    p = str(p or "").strip().replace("R$", "").replace(" ", "")
    if not p:
        return ""
    m = re.search(r"\d+(?:[.,]\d{1,2})?", p)
    if not m:
        return ""
    v = m.group(0).replace(".", ",") if re.fullmatch(r"\d+\.\d{1,2}", m.group(0)) else m.group(0)
    if "," in v:
        a, b = v.split(",", 1); v = f"{a},{(b + '0')[:2]}"
    else:
        v = v + ",00"
    return v[:20]

def _normaliza(j):
    cats = []
    for c in (j.get("categorias") or [])[:20]:
        its = []
        for i in (c.get("itens") or [])[:80]:
            nome = str(i.get("nome") or "").strip()[:60]
            if not nome:
                continue
            inc = bool(i.get("incerto"))
            its.append({"nome": nome, "preco": "" if inc else _preco(i.get("preco")), "desc": str(i.get("desc") or "").strip()[:40],
                        "apartir": bool(i.get("apartir")), "incerto": inc or not _preco(i.get("preco"))})
        if its:
            cats.append({"nome": str(c.get("nome") or "Itens").strip()[:40] or "Itens", "itens": its})
    return {"categorias": cats, "observacoes": str(j.get("observacoes") or "")[:300]}

def _fotos(lista):
    out = []
    for d in (lista or [])[:4]:
        m = re.match(r"^data:image/(jpeg|png|webp);base64,(.+)$", str(d or ""), re.S)
        if not m:
            raise ValueError("foto inválida")
        raw = base64.b64decode(m.group(2))
        if len(raw) > 5_000_000:
            raise ValueError("foto grande demais")
        out.append(("image/" + m.group(1), m.group(2)))
    if not out:
        raise ValueError("mande ao menos uma foto do cardápio")
    return out

def _erro_http(e):
    try:
        return e.read().decode("utf-8", "replace")[:200]
    except Exception:
        return str(e)[:200]

def ler(fotos, setor, chaves, log_dir):
    F = _fotos(fotos)
    prompt = PROMPT.format(setor=setor or "comércio")
    erros = []
    def registrar(prov, modelo, uso=""):
        try:
            with open(os.path.join(log_dir, "ia.log"), "a") as f:
                f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} cardapio {prov} {modelo} fotos={len(F)} {uso}\n")
        except Exception:
            pass
    if chaves.get("ANTHROPIC_KEY"):
        for modelo in ("claude-sonnet-5-5", "claude-haiku-5-5"):
            try:
                conteudo = [{"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}} for mt, b64 in F] + [{"type": "text", "text": prompt}]
                body = json.dumps({"model": modelo, "max_tokens": 8000, "messages": [{"role": "user", "content": conteudo}]}).encode()
                r = _rq.urlopen(_rq.Request("https://api.anthropic.com/v1/messages", data=body, headers={
                    "x-api-key": chaves["ANTHROPIC_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"}), timeout=110)
                j = json.loads(r.read().decode("utf-8", "replace"))
                txt = "".join(b.get("text", "") for b in j.get("content") or [] if b.get("type") == "text")
                res = _normaliza(_limpa_json(txt)); u = j.get("usage") or {}
                registrar("claude", modelo, f"in={u.get('input_tokens')} out={u.get('output_tokens')}")
                return dict(res, provedor=modelo)
            except Exception as e:
                erros.append(f"{modelo}: {_erro_http(e)[:90]}")
    if chaves.get("GEMINI_KEY"):
        modelos = ["gemini-2.5-flash"]
        try:   # os nomes mudam: pega os "flash" de texto disponíveis para a chave
            r = _rq.urlopen(_rq.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200", headers={"x-goog-api-key": chaves["GEMINI_KEY"]}), timeout=20)
            lst = json.loads(r.read().decode("utf-8", "replace")).get("models", [])
            disp = [m["name"].split("/", 1)[1] for m in lst if "flash" in m.get("name", "") and "image" not in m.get("name", "") and "tts" not in m.get("name", "")
                    and "live" not in m.get("name", "") and "generateContent" in (m.get("supportedGenerationMethods") or [])]
            if disp:
                pref = [n for n in disp if re.fullmatch(r"gemini-\d(\.\d)?-flash", n)]
                modelos = (sorted(pref, reverse=True) or sorted(disp, reverse=True))[:3]
        except Exception:
            pass
        # os mais novos às vezes ficam sobrecarregados (503): sempre há os estáveis de reserva
        for reserva in ("gemini-2.5-flash", "gemini-2.0-flash"):
            if reserva not in modelos:
                modelos.append(reserva)
        for modelo in modelos:
            try:
                partes = [{"inlineData": {"mimeType": mt, "data": b64}} for mt, b64 in F] + [{"text": prompt}]
                body = json.dumps({"contents": [{"parts": partes}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}).encode()
                r = _rq.urlopen(_rq.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent", data=body,
                                            headers={"x-goog-api-key": chaves["GEMINI_KEY"], "Content-Type": "application/json"}), timeout=110)
                j = json.loads(r.read().decode("utf-8", "replace"))
                txt = "".join(p.get("text", "") for p in (((j.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []))
                res = _normaliza(_limpa_json(txt)); u = j.get("usageMetadata") or {}
                registrar("gemini", modelo, f"in={u.get('promptTokenCount')} out={u.get('candidatesTokenCount')}")
                return dict(res, provedor=modelo)
            except Exception as e:
                msg = _erro_http(e); erros.append(f"{modelo}: {msg[:90]}")
                if "429" in msg and "quota" in msg.lower():
                    break
    if chaves.get("OPENAI_KEY"):
        try:
            conteudo = [{"type": "text", "text": prompt}] + [{"type": "image_url", "image_url": {"url": f"data:{mt};base64,{b64}"}} for mt, b64 in F]
            body = json.dumps({"model": "gpt-4o-mini", "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": conteudo}]}).encode()
            r = _rq.urlopen(_rq.Request("https://api.openai.com/v1/chat/completions", data=body, headers={
                "Authorization": "Bearer " + chaves["OPENAI_KEY"], "Content-Type": "application/json"}), timeout=110)
            j = json.loads(r.read().decode("utf-8", "replace"))
            res = _normaliza(_limpa_json(j["choices"][0]["message"]["content"])); u = j.get("usage") or {}
            registrar("openai", "gpt-4o-mini", f"in={u.get('prompt_tokens')} out={u.get('completion_tokens')}")
            return dict(res, provedor="gpt-4o-mini")
        except Exception as e:
            erros.append("openai: " + _erro_http(e)[:90])
    raise ValueError(" · ".join(erros) or "nenhuma chave de leitura gravada (Claude, Gemini ou OpenAI)")
