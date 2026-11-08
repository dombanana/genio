# GênIO - Kit de teste: padaria

Este kit contém uma imagem de contexto do setor e dez capas individuais de produto. Cada capa tem câmera, distância e enquadramento próprios. Os materiais estão sem impressão, com textura e iluminação fotográficas para receber depois cores e artes diferentes.

## Arquivos

| Nº | Uso | Arquivo |
| --- | --- | --- |
| 00 | Contexto do setor | 00_contexto_padaria.jpg |
| 01 | Capacho | 01_capacho.jpg |
| 02 | Placa | 02_placa.jpg |
| 03 | Adesivo de vitrine | 03_adesivo_vitrine.jpg |
| 04 | Uniforme polo | 04_uniforme_polo.jpg |
| 05 | Cartão de visita | 05_cartao.jpg |
| 06 | Panfleto | 06_panfleto.jpg |
| 07 | Banner retrátil | 07_banner.jpg |
| 08 | Adesivo de parede | 08_adesivo_parede.jpg |
| 09 | Sacola | 09_sacola.jpg |
| 10 | Carimbo | 10_carimbo.jpg |

O painel é apenas uma folha de conferência. Os arquivos numerados são as imagens individuais para o sistema. A imagem 00 mostra entrada, chão, parede, vitrine e balcão no mesmo ambiente; as capas 01 a 10 valorizam cada produto separadamente. Não usar um recorte do painel como arquivo de produção.

## O que observar neste teste

- O produto deve ser reconhecível pelo objeto e pelo enquadramento.
- A superfície que recebe a arte deve estar visível, com bordas e perspectiva legíveis.
- O contexto deve remeter à mesma padaria: madeira, terrazzo claro, piso terracota e esquadrias em tom petróleo.
- Cores neutras são bases de personalização, não uma limitação da cor a oferecer ao cliente.
- A sacola representa um brinde específico; o carimbo tem sua própria foto. Cartão e panfleto também estão separados. Novos produtos exigem novas capas.

## Marcação dos encaixes, conforme combinado

As imagens são bases fotográficas. A integração marcará as áreas uma única vez. O kit não contém máscaras aferidas nem promete troca automática de cor antes dessa marcação.

Para cada imagem e produto, cadastrar:

1. A máscara do material cuja cor pode mudar.
2. A máscara da área que pode receber impressão.
3. Os quatro cantos do plano de impressão, na ordem topo esquerdo, topo direito, inferior direito e inferior esquerdo; para tecido, um mapa fixo de dobras, se necessário.
4. A margem de segurança e o alinhamento do logotipo.
5. Os elementos que ficam na frente da aplicação, como bordas, parafusos, costuras ou puxadores.
6. O perfil neutro de luz/textura e as cores disponíveis para o produto real.

Fazer essas marcações nos JPGs individuais em tamanho original. O arquivo catalogo_kit.json registra dimensões e hashes; não recortar ou substituir a foto sem versionar e recalibrar.

## Trocar cor e arte sem IA a cada aplicação

Selecionar setor e produto -> carregar a base e as marcações -> aplicar a cor apenas ao material autorizado -> encaixar a arte proporcionalmente no plano frontal -> transformar para a perspectiva da foto -> aplicar textura e luz fixas -> repor oclusões e reflexos -> exportar e guardar em cache.

Cor do material e cor da arte são dados independentes. Não tingir a foto inteira e não recolorir o logotipo ao trocar o material. Não usar multiply como solução universal, porque tinta branca pode desaparecer. Preservar a proporção da marca e usar contain, sem cortar nome ou símbolo.

Na vitrine e na parede, vinil recortado usa a transparência da arte: não criar um retângulo branco ao redor. A cor do vinil não é a cor do vidro. Uma versão monocromática da marca deve ser aprovada antes de aplicar cor de recorte. No carimbo, a impressão entra na área da folha; o corpo preto do aparelho e sua pequena etiqueta são superfícies distintas. Carimbo precisa de versão monocromática própria.

Papel branco e kraft podem exigir texturas e perfis diferentes; camiseta branca e azul devem preservar tecido e sombras; borda e centro do capacho podem ter controles de cor separados. Oferecer apenas as cores e técnicas disponíveis no produto real.

Para uniforme, o peito esquerdo é o de quem veste, que aparece à direita para quem olha a pessoa de frente. Para sacola e polo, não deformar a marca por IA: usar um mapa fixo calibrado, mantendo a mesma fotografia.

## Arquivos e fabricação

As imagens são prévias de apresentação. A arte de impressão sai do layout frontal em tamanho físico, sem perspectiva, reflexos ou sombras do mockup. Medidas, sangria e limitações de fabricação devem vir do fornecedor.

O conjunto foi criado como fotografias sintéticas pelo gerador de imagens. Os prompts de cada capa estão no arquivo prompts_kit.json, para documentar a preparação inicial. A operação recorrente de troca de cor e arte deve ser uma rotina determinística.
