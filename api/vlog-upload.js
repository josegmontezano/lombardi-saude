import { handleUpload } from '@vercel/blob/client';
import crypto from 'node:crypto';

function checkAuthorization(token){
  if(!process.env.DJANGO_SECRET_KEY) throw Error('Serviço indisponível');
  if(typeof token!=='string'||!token.includes('.')) throw Error('Acesso não autorizado');
  const [payload,signature]=token.split('.');
  if(!/^[a-zA-Z0-9_-]{4,120}$/.test(payload)||!/^[0-9a-f]{64}$/.test(signature))throw Error('Assinatura inválida');
  const expected=crypto.createHmac('sha256',process.env.DJANGO_SECRET_KEY).update(payload).digest('hex');
  if(!crypto.timingSafeEqual(Buffer.from(signature,'hex'),Buffer.from(expected,'hex')))throw Error('Assinatura inválida');
  const decoded=Buffer.from(payload,'base64url').toString('utf8');
  const [user,ts]=decoded.split(':');
  if(!/^[1-9][0-9]{0,10}$/.test(user)||!/^[0-9]{10}$/.test(ts)||Math.abs(Date.now()/1000-Number(ts))>15*60)throw Error('Assinatura expirada');
  return user;
}
export default async function handler(request,response){
 if(request.method!=='POST')return response.status(405).json({error:'Método não permitido'});
 try{
   const data=typeof request.body==='string'?JSON.parse(request.body):request.body;
   const out=await handleUpload({body:data,request,
     onBeforeGenerateToken:async (pathname,clientPayload)=>{
       const userId=checkAuthorization(clientPayload);
       if(typeof pathname!=='string'||!pathname.startsWith('vlog/')||pathname.length>200||pathname.includes('..'))throw Error('Nome de arquivo inválido');
       return {allowedContentTypes:['video/mp4','video/webm','video/quicktime','image/jpeg','image/png','image/webp'],maximumSizeInBytes:2*1024*1024*1024,addRandomSuffix:true,tokenPayload:JSON.stringify({userId})};
     },
     onUploadCompleted:async()=>{} });
   return response.status(200).json(out);
 }catch(e){return response.status(400).json({error:'Falha no upload: '+String(e.message||'indisponível')});}
}
