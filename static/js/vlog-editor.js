import {upload} from 'https://esm.sh/@vercel/blob@2/client?bundle';
const form=document.querySelector('#vlog-editor');
if(form){
 let busy=0;const submit=form.querySelector('#vlog-publish-button');
 const priv=form.dataset.privateEnabled==='1';
 for(const [id,field,statusId] of [['vlog-video-file','id_private_media_path','vlog-upload-status'],['vlog-cover-file','id_cover_url','cover-status']]){
  const input=document.getElementById(id),status=document.getElementById(statusId);
  input?.addEventListener('change',async()=>{
   if(!input.files?.length)return;const file=input.files[0];const isVideo=id==='vlog-video-file';
   if(isVideo&&!priv){status.textContent='Envio de vídeo protegido indisponível até conectar o armazenamento privado.';return;}
   if(!((isVideo&&['video/mp4','video/webm','video/quicktime'].includes(file.type))||(!isVideo&&['image/jpeg','image/png','image/webp'].includes(file.type)))){status.textContent='Formato não permitido.';return;}
   busy++;submit.disabled=true;status.textContent='Enviando arquivo...';
   const progress=document.getElementById('vlog-upload-progress');if(isVideo&&progress){progress.hidden=false;progress.value=0;}
   try{
    if(isVideo){
      const response=await fetch('/api/vlog-private',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'upload',ticket:form.dataset.uploadAuth,filename:file.name,size:file.size,type:file.type})});
      const data=await response.json();if(!response.ok)throw Error(data.error||'Erro de autorização');
      const sent=await fetch(data.url,{method:'PUT',body:file,headers:{'Content-Type':file.type}});if(!sent.ok)throw Error('O armazenamento privado recusou o arquivo.');
      document.getElementById(field).value=data.pathname; document.getElementById('id_media_url').value='';
      if(progress)progress.value=100;
    }else{
      const clean=file.name.replace(/[^a-zA-Z0-9._-]/g,'-');
      const blob=await upload('vlog/'+Date.now()+'-'+clean,file,{access:'public',handleUploadUrl:'/api/vlog-upload',clientPayload:form.dataset.uploadAuth,multipart:file.size>5*1024*1024});
      document.getElementById(field).value=blob.url;
    }
    status.textContent='Arquivo armazenado. Clique em Salvar publicação.';
   }catch(e){status.textContent='Falha: '+(e?.message||'Tente novamente');}
   finally{busy--;submit.disabled=busy>0;}
  });
 }
 form.addEventListener('submit',e=>{if(busy){e.preventDefault();alert('Aguarde o upload terminar.')}});
}
