# GênIO — como a inteligência deve montar os materiais

## 1. O que há neste pacote

Há 14 setores e 16 tipos de produto por setor. COM_ARTE é a demonstração;
SEM_ARTE é a referência neutra. Artes_Frontais contém maquetes vetoriais em SVG
e sua renderização JPG. Fotos_Produtos contém cenas fotográficas sintéticas,
quando o par estiver disponível. O arquivo STATUS_PRODUCAO.json informa a
quantidade real disponível e os itens pendentes. Nunca tratar uma maquete
frontal como se fosse uma fotografia de produto aplicada no ambiente.

O primeiro kit da padaria está preservado em 03_Padaria/Primeiro_Kit_Original.
Os IDs dos produtos são estáveis e iguais entre os setores. Um arquivo por
produto e por versão; painéis de conferência nunca substituem esses arquivos.

## 2. Precedência da identidade e das cores

1. Usar a identidade do cliente, quando fornecida e aprovada.
2. Respeitar uma escolha explícita do cliente.
3. Na ausência dessas duas fontes, usar a paleta de referência do setor.

Padaria: amarelo e dourado. Cafeteria: marrom. Restaurante: verde, branco e
vermelho. As demais paletas estão na tabela abaixo e em REGRAS_MONTAGEM.json.
São escolhas deste projeto, não afirmações de que um ramo tenha cor obrigatória.
Não transformar uma padaria que já tem identidade azul em amarela sem autorização.
Não pintar paredes, piso, móveis ou toda a fotografia para impor a cor do ramo.

Distribuição sugerida para uma arte nova: 60% base neutra, 30% principal,
10% destaque. É referência de composição, não porcentagem rígida em cada produto.
Cor do material, cor da arte e cor do logotipo são três decisões distintas.
Um produto escuro pode usar marca branca mesmo num setor associado ao dourado.
Na padaria do primeiro kit, petróleo, creme e dourado formam uma variação de
identidade já ilustrada; isso não muda a paleta de partida dos novos clientes.

## 3. Separar as camadas antes de montar

A. Foto de ambiente original: imutável.
B. Máscara do produto/material que pode mudar de cor.
C. Máscara e plano que podem receber impressão.
D. Arte frontal do produto, com texto e logotipo em proporção correta.
E. Textura, iluminação e dobras do material.
F. Oclusões: costuras, bordas, parafusos, puxadores, molduras e reflexos.

Registrar os quatro cantos do plano de impressão: superior esquerdo, superior
direito, inferior direito, inferior esquerdo, em pixels e em coordenadas
normalizadas. Para roupa, boné e bandeira, usar mapa de deformação próprio.
Os pares deste catálogo NÃO contêm máscaras ou homografias já aferidas.
Não preencher números de calibração por estimativa e apresentá-los como medidos.

## 4. Passo a passo de uma montagem

1. Receber setor, produto, dados do cliente, logo e identidade disponíveis.
2. Conferir a origem de nome, CNPJ, contato e endereço. Não inventar campos.
3. Resolver a paleta pela precedência da seção 2 e registrar a origem da escolha.
4. Separar material de impressão e arte. Escolher somente cores e processos
   realmente oferecidos pelo fornecedor.
5. Selecionar a variante aprovada do logo: original, branca, preta ou negativa.
6. Escolher fundo e texto com contraste; preservar os tons originais da marca.
   Nunca usar marca roxa sobre camisa roxa. Não tornar branco transparente por
   aplicar multiply indiscriminadamente.
7. Gerar o layout frontal, com hierarquia, margens e área reservada do produto.
8. Validar o layout frontal: grafia, acento, dados, proporções, legibilidade e QR.
9. Aplicar a arte no plano calibrado; manter contain e não cortar a marca.
10. Aplicar textura/luz fixas e recolocar oclusões por cima. Não mudar o ambiente.
11. Exportar a prévia aplicada e a versão neutra usando a mesma câmera e corte.
12. Salvar os arquivos com ID estável, versão, dimensões e hash. Invalidar a
    calibração se a foto-base, o recorte ou a dimensão forem substituídos.
13. Antes da fabricação, gerar outra saída: arte frontal no tamanho físico,
    sem perspectiva, sombras ou reflexos do mockup. Aplicar sangria, área segura,
    perfil de cor e limitações do fornecedor. A foto de prévia não vai à gráfica.

## 5. Regras específicas por produto

- Capacho: margem e borda preservadas; limitar a paleta às cores do fabricante;
  não criar degradê se o processo usa recorte/pintura por calques.
- Placa: manter furos, espaçadores e margem; não imprimir sobre ferragens.
- Vitrine: vinil recortado usa transparência; não inserir um retângulo branco.
- Polo e camiseta: peito esquerdo é o de quem veste (direita de quem olha).
  Respeitar dobras, área de bordado/impressão, traço mínimo e cores de linha.
- Cartão: logo em área própria; uma caixa colorida deve conter tanto o QR quanto
  os dados. Dentro dela, o QR conserva sua área branca independente.
- Flyer: cardápio em alimentação; lista de produtos ou serviços nos demais ramos.
  Não preencher todos os setores com os mesmos itens de café.
- Banner retrátil: preservar haste, base e proporção do painel.
- Parede: usar setas e destinos reais. Não inferir rotas pela cor ou inventar
  setores inexistentes na loja. Direções do catálogo são ilustrativas.
- Ecobag: controlar área frontal e manter alças, costuras e dobras livres.
- Carimbos: impressão monocromática. Cada folha demonstra um carimbo diferente;
  o carimbo comercial com dados da empresa fica na última folha, mais próxima
  e visível. Não misturar tinta do carimbo com a cor do corpo do aparelho.
- Wind banner: bandeira de vento, não roll-up. Girar a linha de texto inteira
  em 90 graus para leitura de lado; não empilhar uma letra de cada vez. Usar o
  gabarito real do fabricante para formato, haste, costura e área segura.
- Faixa: formato horizontal, com ilhós e amarração fora da arte útil.
- Folheto: três painéis e dobras previstos; textos não atravessam a dobra sem
  intenção. Não confundir o folheto com o flyer-cardápio.
- Boné: respeitar a área frontal e a costura central; não deformar o logo.
- Avental: marca no peito; alças e bolsos são camadas físicas independentes.

## 6. Contraste e leitura

Para textos digitais, usar como referência WCAG: mínimo 4,5:1 para texto comum
e 3:1 para texto grande. O projeto também adota 4,5:1 para o logotipo como regra
interna, embora a WCAG tenha exceção para logotipos. Não declarar uma impressão
ou bordado como certificado por cumprir uma simulação de contraste em RGB.
Quando a cor principal não permitir texto branco legível, usar a variante escura
aprovada, uma área neutra ou outro fundo. Não resolver alterando a marca sem fonte.
Legibilidade não pode depender apenas de distinguir vermelho de verde: rotas e
estados precisam de palavras, setas, símbolos ou formas.

## 7. QR e dados de exemplo

Gerar o QR a partir do endereço real do cliente, não desenhá-lo por IA. Usar
módulos escuros sobre branco e quiet zone de pelo menos quatro módulos em todos
os lados. Não esticar, cortar, cobrir com logo ou encostar texto nessa margem.
Decodificar a saída e testar o tamanho final antes de imprimir.
Os QR das ARTES FRONTAIS apontam para example.com e são demonstrativos.
Os QR das FOTOGRAFIAS SINTÉTICAS são apenas ilustrações e podem não funcionar.
O CNPJ 00.000.000/0000-00 é propositalmente inválido. Nenhuma arte com dados
fictícios deve ser liberada para produção final sem substituição e validação.

## 8. Entrega e revisão

Saídas diferentes: prévia fotográfica, arte frontal editável e arquivo final do
fornecedor. Manter esses tipos separados. Gerar registro de paleta, variante do
logo, produto, dimensões, versão, origem dos dados e status da calibração.
Se faltar informação, marcar pendência; não usar a foto de ambiente como logo,
não inventar dado e não atribuir ao mockup precisão física não aferida.

## Referências técnicas

- W3C, contraste: https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
- DENSO WAVE, margem do QR: https://www.qrcode.com/en/howto/code.html

## Paletas de partida por setor

| Setor | Principal | Destaque | Fundo | Texto |
|---|---|---|---|---|
| Cafeteria | #59382D | #C98245 | #FFF9F1 | #2B201A |
| Restaurante | #1F6B45 | #C44236 | #FFFFFF | #173C29 |
| Padaria | #D4A124 | #CE8D18 | #FFF9E8 | #51280F |
| Clínica | #126D80 | #84B8B8 | #FFFFFF | #163C43 |
| Clínica estética | #775467 | #BD9F82 | #FFFAF7 | #372C34 |
| Salão | #37303D | #BD8E6A | #FAF7F2 | #29222F |
| Imobiliária | #243E61 | #C49A56 | #FFFFFF | #1B2C43 |
| Loja de roupas | #4F394B | #C0969D | #FFFAFC | #30242D |
| Pet shop | #176E73 | #E1A34F | #FFFCF4 | #133F42 |
| Farmácia | #1C7861 | #79B7AC | #FFFFFF | #173D31 |
| Academia | #203746 | #C1B538 | #FFFFFF | #182A36 |
| Autopeças/oficina | #34434F | #D37C25 | #FFFFFF | #24313A |
| Escritório/serviços | #334C62 | #7FA3AC | #FFFFFF | #233444 |
| Mercado | #466B38 | #D9A637 | #FFFCF4 | #2B4022 |


## Reaproveitamento aprovado

Os 14 setores têm os 16 produtos em pares COM_ARTE e SEM_ARTE. Parte dos pares é compartilhada por autorização do usuário. O catálogo não representa 448 fotografias únicas.

Oficina, mercado e farmácia têm cenas próprias de capacho, adesivo de parede com rotas e wind banner. Os demais materiais que estavam pendentes usam o par genérico GIO de 00_Bases_Compartilhadas. Pares setoriais já concluídos foram preservados.

REAPROVEITAMENTO.json identifica a origem e o modo por produto. No modo ambas_variantes_genericas, COM_ARTE é uma demonstração neutra GIO, sem denominação do ramo. Essa imagem não deve ser apresentada como a personalização pronta daquele setor. Carregar a SEM_ARTE correspondente e aplicar a arte frontal específica de Artes_Frontais, após calibração. Os dois arquivos genéricos são copiados juntos para manter o enquadramento pareado.

A paleta azul da demonstração genérica não substitui as paletas setoriais. A identidade aprovada do cliente continua tendo prioridade. Não reutilizar texto de outro ramo: cardápio para alimentação, catálogo de produtos/serviços nos demais.

Imobiliária e escritório podem compartilhar a área de atendimento. Bases de roupa e papelaria da loja de roupas também podem ser reutilizadas. Fundos clínicos neutros servem como referência de balcão da farmácia; fundos de panificação servem como referência do mercado. Não usar esse reaproveitamento para afirmar que uma clínica é um mercado ou que uma oficina funciona num escritório.

Os ambientes gerais são referências de contexto. Cada produto continua em arquivo individual. Máscaras, planos e deformações precisam de calibração por foto-base; cópias idênticas podem reutilizar a mesma calibração, identificada pelo SHA-256.
