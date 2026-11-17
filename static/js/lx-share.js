(function(){'use strict';
 function cleanLink(el){const article=el.closest('.lx-vlog-card,.lx-ig-card,.lx-ux-question,.lx-report')||document;const direct=article.querySelector('a[href*="/vlog/"],a[href*="instagram.com/"]');try{return new URL(direct?.href || location.href,location.href).href}catch(_){return location.href}}
 function status(el,text){const x=el.closest('.lx-share-actions')?.querySelector('.lx-share-feedback');if(x)x.textContent=text}
 async function copy(text){if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(text)}else{const a=document.createElement('textarea');a.value=text;document.body.appendChild(a);a.select();document.execCommand('copy');a.remove()}}
 document.addEventListener('click',async function(event){const btn=event.target.closest('.lx-share-ig,.lx-share-wa,.lx-share-copy');if(!btn)return;const cont=btn.closest('.lx-share-actions');if(!cont)return;const url=cleanLink(btn),title=cont.dataset.shareTitle||document.title;
 if(btn.matches('.lx-share-wa')){btn.href='https://api.whatsapp.com/send?text='+encodeURIComponent(title+'\n'+url);return}
 event.preventDefault();if(btn.matches('.lx-share-copy')){try{await copy(url);status(btn,'Link copiado.')}catch(_){status(btn,'Não foi possível copiar automaticamente.')}return}
 if(navigator.share){try{await navigator.share({title,text:title,url});status(btn,'Escolha o aplicativo para compartilhar.');return}catch(e){if(e.name==='AbortError')return}}
 try{await copy(url);status(btn,'Link copiado. Abra o Instagram e cole o endereço na publicação ou mensagem.')}catch(_){status(btn,'Copie o endereço da página para compartilhar no Instagram.')} },true);
})();
