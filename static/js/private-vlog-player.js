(() => {
 'use strict';
 const video=document.querySelector('#private-vlog-player'); if(!video)return;
 const notice=document.querySelector('#private-playback-message');
 async function refresh(){
  try{
   const r=await fetch('/api/vlog-private',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'play',ticket:video.dataset.playbackTicket}),cache:'no-store'});
   const b=await r.json(); if(!r.ok)throw Error(b.error||'Indisponível');
   video.src=b.url; video.load(); if(notice)notice.textContent='';
  }catch(e){if(notice)notice.textContent='Vídeo indisponível: '+e.message;}
 }
 refresh();
 video.addEventListener('contextmenu',ev=>ev.preventDefault());
})()
