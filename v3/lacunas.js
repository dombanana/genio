// GenIO — as caixinhas do manual de identidade: tudo que o manual precisa ter, de onde cada uma vem e em que estado está.
// Estados: pendente · encontrado (público) · porta (foto/anotação na visita) · derivado (criado a partir do que já foi preenchido) · confirmado (o cliente aprovou)
// Origem esperada, na ordem em que o sistema tenta: publico → porta → derivado → cliente
const Lacunas=(()=>{
  // tipo: texto | imagem | cor | derivado | ok (só confirmação)
  const L=[
    // Empresa
    {g:"Empresa",id:"nome",n:"Nome da empresa",t:"texto",o:"publico"},
    {g:"Empresa",id:"leitura",n:"Como se lê / escreve",t:"texto",o:"cliente",opc:true,dica:"ex.: Gen.io lê Gênio"},
    {g:"Empresa",id:"setor",n:"Setor",t:"texto",o:"rota"},
    {g:"Empresa",id:"tel",n:"Telefone / WhatsApp",t:"texto",o:"publico"},
    {g:"Empresa",id:"endereco",n:"Endereço",t:"texto",o:"publico"},
    {g:"Empresa",id:"site",n:"Site",t:"texto",o:"publico",opc:true},
    {g:"Empresa",id:"redes",n:"Instagram · Facebook",t:"texto",o:"publico",opc:true},
    {g:"Empresa",id:"registro",n:"Registro profissional (CRECI, CRM, OAB…)",t:"texto",o:"publico",opc:true},
    {g:"Empresa",id:"sobre",n:"Quem somos (1–2 frases)",t:"texto",o:"publico"},
    {g:"Empresa",id:"slogan",n:"Slogan",t:"texto",o:"cliente",opc:true,dica:"se não tem, não inventar"},
    {g:"Empresa",id:"horario",n:"Horário de atendimento",t:"texto",o:"porta"},
    {g:"Empresa",id:"servicos",n:"Serviços principais (3 a 5)",t:"texto",o:"publico"},
    // Marca
    {g:"Marca",id:"logoOriginal",n:"Logo original (melhor arquivo)",t:"imagem",o:"publico"},
    {g:"Marca",id:"logoVetor",n:"Logo em vetor, fiel ao original",t:"derivado",o:"derivado",conf:true},
    {g:"Marca",id:"removido",n:"O que saiu e por quê (degradê, brilho, sombra, decoração)",t:"derivado",o:"derivado"},
    {g:"Marca",id:"simbolo",n:"Símbolo sozinho",t:"derivado",o:"derivado",opc:true},
    {g:"Marca",id:"lockups",n:"Marca horizontal · vertical",t:"derivado",o:"derivado"},
    {g:"Marca",id:"versoes",n:"Versões: cor · uma cor preta · uma cor branca · negativo",t:"derivado",o:"derivado"},
    {g:"Marca",id:"borda",n:"Marca com borda (para fundo de foto)",t:"derivado",o:"derivado"},
    {g:"Marca",id:"tamanhoMin",n:"Tamanho mínimo por material",t:"derivado",o:"derivado"},
    {g:"Marca",id:"respiro",n:"Área de respiro",t:"derivado",o:"derivado"},
    {g:"Marca",id:"proibicoes",n:"Proibições (esticar, girar, trocar fonte…)",t:"derivado",o:"derivado"},
    // Cores
    {g:"Cores",id:"corPrincipal",n:"Cor principal",t:"cor",o:"publico",conf:true},
    {g:"Cores",id:"corApoio",n:"Cor de apoio",t:"cor",o:"publico",opc:true,conf:true},
    {g:"Cores",id:"corFundo",n:"Fundo preferido (o do logo original)",t:"derivado",o:"derivado"},
    {g:"Cores",id:"materiais",n:"Tradução por material: bobina · CMYK · vinil · camiseta",t:"derivado",o:"derivado"},
    {g:"Cores",id:"combinacoes",n:"Combinações marca × fundo permitidas e proibidas",t:"derivado",o:"derivado"},
    // Tipografia
    {g:"Tipografia",id:"fonteMarca",n:"Fonte da marca (ou equivalente livre)",t:"derivado",o:"derivado"},
    {g:"Tipografia",id:"fonteApoio",n:"Fonte de apoio (telefone, endereço, textos)",t:"derivado",o:"derivado"},
    // Local (na porta)
    {g:"Local",id:"fachada",n:"Fachada com o cartão-régua",t:"imagem",o:"porta"},
    {g:"Local",id:"entrada",n:"Medida da entrada (cm)",t:"texto",o:"porta"},
    {g:"Local",id:"vitrine",n:"Vitrine (foto)",t:"imagem",o:"porta",opc:true},
    {g:"Local",id:"materialAtual",n:"Material atual (placa, cartão, uniforme)",t:"imagem",o:"porta",opc:true},
    // Aprovação
    {g:"Aprovação",id:"okMarca",n:"Cliente aprovou a marca em vetor",t:"ok",o:"cliente"},
    {g:"Aprovação",id:"okCores",n:"Cliente aprovou as cores",t:"ok",o:"cliente"},
  ];
  const ORIGEM={publico:"público",porta:"na porta",derivado:"derivado",cliente:"cliente",rota:"rota"};
  const ESTADO={pendente:"pendente",encontrado:"encontrado",porta:"na porta",derivado:"derivado",confirmado:"confirmado",nao:"não tem"};
  const grupos=()=>[...new Set(L.map(x=>x.g))];
  // estado efetivo de cada caixinha a partir do registro do cliente (o.lacunas) e do que já existe nele (nome, tel, logos, manual)
  function estado(o){const v=(o&&o.lacunas)||{},r={};
    for(const x of L){const e=v[x.id];
      if(e&&e.estado){r[x.id]=e;continue;}
      let auto=null;
      if(x.id==="nome"&&o&&o.nome)auto={estado:"encontrado",valor:o.nome,origem:"rota"};
      if(x.id==="tel"&&o&&o.tel)auto={estado:"encontrado",valor:o.tel,origem:"rota"};
      if(x.id==="logoOriginal"&&o&&o.logos&&o.logos.length)auto={estado:"encontrado",valor:o.logos[0].src,origem:"porta"};
      if(x.id==="corPrincipal"&&o&&o.manual&&o.manual.cores&&o.manual.cores[0])auto={estado:"derivado",valor:o.manual.cores[0].hex,nome:o.manual.cores[0].nome,origem:"derivado"};
      if(x.id==="corApoio"&&o&&o.manual&&o.manual.cores&&o.manual.cores[1])auto={estado:"derivado",valor:o.manual.cores[1].hex,nome:o.manual.cores[1].nome,origem:"derivado"};
      r[x.id]=auto||{estado:"pendente"};}
    return r;}
  const feitas=r=>L.filter(x=>["encontrado","porta","derivado","confirmado","nao"].includes((r[x.id]||{}).estado)).length;
  return {L,ORIGEM,ESTADO,grupos,estado,feitas};
})();
