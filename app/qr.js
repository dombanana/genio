/* GênIO · codificador QR próprio (byte mode, versões 1–10, correção M). Sem dependências.
   Uso: QR.matriz("https://…") → {n, m:[[0|1]]}; QR.desenhar(g,texto,x,y,tamanho,cor) */
(function(){
  // ---- GF(256)
  const EXP=new Uint8Array(512),LOG=new Uint8Array(256);{let x=1;for(let i=0;i<255;i++){EXP[i]=x;LOG[x]=i;x<<=1;if(x&256)x^=0x11d;}for(let i=255;i<512;i++)EXP[i]=EXP[i-255];}
  const mul=(a,b)=>a&&b?EXP[LOG[a]+LOG[b]]:0;
  function gerador(n){let g=[1];for(let i=0;i<n;i++){const ng=new Array(g.length+1).fill(0);for(let j=0;j<g.length;j++){ng[j]^=g[j];ng[j+1]^=mul(g[j],EXP[i]);}g=ng;}return g;}
  function rs(dados,n){const g=gerador(n);const r=new Array(n).fill(0);for(const d of dados){const f=d^r[0];r.shift();r.push(0);if(f)for(let j=0;j<n;j++)r[j]^=mul(g[j+1],f);}return r;}
  // ---- tabela nível M: [total codewords, ec por bloco, blocos g1, dados g1, blocos g2, dados g2]
  const TAB={1:[26,10,1,16,0,0],2:[44,16,1,28,0,0],3:[70,26,1,44,0,0],4:[100,18,2,32,0,0],5:[134,24,2,43,0,0],6:[172,16,4,27,0,0],7:[196,18,4,31,0,0],8:[242,22,2,38,2,39],9:[292,22,3,36,2,37],10:[346,26,4,43,1,44]};
  const ALINH={2:[6,18],3:[6,22],4:[6,26],5:[6,30],6:[6,34],7:[6,22,38],8:[6,24,42],9:[6,26,46],10:[6,28,50]};
  function bytes(t){return Array.from(new TextEncoder().encode(t));}
  function matriz(texto){const B=bytes(texto);let v=1;for(;v<=10;v++){const T=TAB[v];const cap=T[2]*T[3]+T[4]*T[5];const ind=v<10?8:16;if(4+ind+B.length*8<=cap*8)break;}if(v>10)throw new Error("texto longo demais para o QR");
    const T=TAB[v],n=17+4*v,ind=v<10?8:16,capD=T[2]*T[3]+T[4]*T[5];
    // bits de dados
    const bits=[];const put=(val,len)=>{for(let i=len-1;i>=0;i--)bits.push((val>>i)&1);};put(4,4);put(B.length,ind);B.forEach(b=>put(b,8));
    for(let i=0;i<4&&bits.length<capD*8;i++)bits.push(0);while(bits.length%8)bits.push(0);
    const cw=[];for(let i=0;i<bits.length;i+=8){let x=0;for(let j=0;j<8;j++)x=(x<<1)|bits[i+j];cw.push(x);}
    for(let k=0;cw.length<capD;k++)cw.push(k%2?0x11:0xec);
    // blocos + entrelaçamento
    const blocos=[];let p=0;for(let i=0;i<T[2];i++){blocos.push(cw.slice(p,p+T[3]));p+=T[3];}for(let i=0;i<T[4];i++){blocos.push(cw.slice(p,p+T[5]));p+=T[5];}
    const ecs=blocos.map(b=>rs(b,T[1]));const seq=[];const maxD=Math.max(T[3],T[5]);
    for(let i=0;i<maxD;i++)for(const b of blocos)if(i<b.length)seq.push(b[i]);for(let i=0;i<T[1];i++)for(const e of ecs)seq.push(e[i]);
    // módulos
    const m=Array.from({length:n},()=>new Array(n).fill(0)),fixo=Array.from({length:n},()=>new Array(n).fill(false));
    const set=(r,c,val)=>{m[r][c]=val;fixo[r][c]=true;};
    const buscador=(r0,c0)=>{for(let r=-1;r<=7;r++)for(let c=-1;c<=7;c++){const rr=r0+r,cc=c0+c;if(rr<0||cc<0||rr>=n||cc>=n)continue;const on=(r>=0&&r<=6&&(c===0||c===6))||(c>=0&&c<=6&&(r===0||r===6))||(r>=2&&r<=4&&c>=2&&c<=4);set(rr,cc,on?1:0);}};
    buscador(0,0);buscador(0,n-7);buscador(n-7,0);
    for(let i=8;i<n-8;i++){set(6,i,i%2?0:1);set(i,6,i%2?0:1);}
    const al=ALINH[v]||[];for(const r of al)for(const c of al){if(fixo[r][c])continue;for(let dr=-2;dr<=2;dr++)for(let dc=-2;dc<=2;dc++){const on=Math.max(Math.abs(dr),Math.abs(dc))!==1;set(r+dr,c+dc,on?1:0);}}
    // reserva de formato
    for(let i=0;i<9;i++){if(i<n){fixo[8][i]=true;fixo[i][8]=true;}}for(let i=0;i<8;i++){fixo[8][n-1-i]=true;fixo[n-1-i][8]=true;}set(n-8,8,1);
    // dados em zigue-zague
    let bi=0;const total=seq.length*8;const bit=i=>i<total?(seq[i>>3]>>(7-(i&7)))&1:0;
    for(let col=n-1;col>0;col-=2){if(col===6)col--;for(let k=0;k<n;k++){const r=((n-1-col)>>1)%2===0?n-1-k:k;for(const c of [col,col-1]){if(!fixo[r][c]){m[r][c]=bit(bi++);}}}}
    // máscara: escolhe a de menor penalidade
    const MASC=[(r,c)=>(r+c)%2===0,(r,c)=>r%2===0,(r,c)=>c%3===0,(r,c)=>(r+c)%3===0,(r,c)=>(Math.floor(r/2)+Math.floor(c/3))%2===0,(r,c)=>(r*c)%2+(r*c)%3===0,(r,c)=>((r*c)%2+(r*c)%3)%2===0,(r,c)=>((r+c)%2+(r*c)%3)%2===0];
    function aplicar(mi){const o=m.map(l=>l.slice());for(let r=0;r<n;r++)for(let c=0;c<n;c++)if(!fixo[r][c]&&MASC[mi](r,c))o[r][c]^=1;formato(o,mi);return o;}
    function formato(o,mi){let f=(0b00<<3)|mi;let d=f<<10;for(let i=14;i>=10;i--)if((d>>i)&1)d^=0x537<<(i-10);const F=((f<<10)|d)^0x5412;const b=i=>(F>>i)&1;
      for(let i=0;i<6;i++){o[8][i]=b(14-i);o[i][8]=b(i);}o[8][7]=b(8);o[8][8]=b(7);o[7][8]=b(6);
      for(let i=0;i<8;i++)o[n-1-i][8]=b(14-i);for(let i=0;i<7;i++)o[8][n-7+i]=b(6-i);o[n-8][8]=1;}
    function penal(o){let p=0;for(let r=0;r<n;r++){let run=1;for(let c=1;c<n;c++){if(o[r][c]===o[r][c-1]){run++;if(run===5)p+=3;else if(run>5)p++;}else run=1;}}
      for(let c=0;c<n;c++){let run=1;for(let r=1;r<n;r++){if(o[r][c]===o[r-1][c]){run++;if(run===5)p+=3;else if(run>5)p++;}else run=1;}}
      for(let r=0;r<n-1;r++)for(let c=0;c<n-1;c++){const s=o[r][c]+o[r][c+1]+o[r+1][c]+o[r+1][c+1];if(s===0||s===4)p+=3;}
      let esc=0;for(let r=0;r<n;r++)for(let c=0;c<n;c++)esc+=o[r][c];const k=Math.floor(Math.abs(esc*100/(n*n)-50)/5);p+=k*10;return p;}
    let melhor=null,mp=Infinity;for(let mi=0;mi<8;mi++){const o=aplicar(mi);const pp=penal(o);if(pp<mp){mp=pp;melhor=o;}}
    return {n,m:melhor,versao:v};}
  function desenhar(g,texto,x,y,s,cor,fundo){const q=matriz(texto);const zona=2;const mod=s/(q.n+2*zona);if(fundo!==null){g.fillStyle=fundo||"#FFFFFF";g.fillRect(x,y,s,s);}g.fillStyle=cor||"#000";
    for(let r=0;r<q.n;r++)for(let c=0;c<q.n;c++)if(q.m[r][c])g.fillRect(x+(c+zona)*mod,y+(r+zona)*mod,mod+0.3,mod+0.3);return q;}
  window.QR={matriz,desenhar};
})();
