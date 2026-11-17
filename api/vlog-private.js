import {issueSignedToken,presignUrl} from '@vercel/blob';
import crypto from 'node:crypto';
const getSecret=()=>process.env.DJANGO_SECRET_KEY||'';
function signedPayload(ticket){
 if(!getSecret()||typeof ticket!=='string'||ticket.length>1300)throw Error('Autorização inválida');
 const [payload,signature,extra]=ticket.split('.');
 if(extra||!/^[A-Za-z0-9_-]+$/.test(payload||'')||!/^[a-f0-9]{64}$/.test(signature||''))throw Error('Assinatura inválida');
 const actual=crypto.createHmac('sha256',getSecret()).update(payload).digest('hex');
 if(!crypto.timingSafeEqual(Buffer.from(actual),Buffer.from(signature)))throw Error('Assinatura inválida');
 return Buffer.from(payload,'base64url').toString('utf8');
}
function checkEditor(ticket){
 const parts=signedPayload(ticket).split(':');const id=parts[0],ts=parts[1];
 if(parts.length!==2||!/^[1-9][0-9]{0,11}$/.test(id)||!/^[0-9]{10}$/.test(ts)||Math.abs(Date.now()/1000-Number(ts))>12*60)throw Error('Autorização expirada');
 return id;
}
function checkPlayback(ticket){
 let content;try{content=JSON.parse(signedPayload(ticket))}catch{throw Error('Conteúdo inválido')}
 if(!content||!Number.isSafeInteger(content.post)||!Number.isSafeInteger(content.ts)||Math.abs(Date.now()/1000-content.ts)>120||!/^vlog\/private\/[0-9]{1,12}\/[0-9a-f]{32}\.(mp4|webm|mov)$/.test(content.path))throw Error('Autorização expirada');
 return content.path;
}
const supported={'video/mp4':'mp4','video/webm':'webm','video/quicktime':'mov'};
export default async function handler(req,res){
 res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');
 if(req.method!=='POST')return res.status(405).json({error:'Método não permitido'});
 if(!process.env.VLOG_PRIVATE_READ_WRITE_TOKEN)return res.status(503).json({error:'Armazenamento privado não conectado'});
 try{
 const data=typeof req.body==='string'?JSON.parse(req.body):req.body||{};
 const accessToken=process.env.VLOG_PRIVATE_READ_WRITE_TOKEN;
 if(data.action==='upload'){
   const user=checkEditor(data.ticket);
   if(!supported[data.type]||!Number.isSafeInteger(data.size)||data.size<100||data.size>512*1024*1024)throw Error('Vídeo deve ser MP4, WebM ou MOV com até 512 MB por arquivo');
   const name=`vlog/private/${user}/${crypto.randomBytes(16).toString('hex')}.${supported[data.type]}`;
   const until=Date.now()+12*60*1000;
   const token=await issueSignedToken({token:accessToken,pathname:name,operations:['put'],validUntil:until,allowedContentTypes:[data.type],maximumSizeInBytes:data.size});
   const {presignedUrl}=await presignUrl(token,{operation:'put',pathname:name,validUntil:until,allowedContentTypes:[data.type],maximumSizeInBytes:data.size});
   return res.status(200).json({url:presignedUrl,pathname:name});
 }
 if(data.action==='play'){
   const pathname=checkPlayback(data.ticket),until=Date.now()+15*60*1000;
   const token=await issueSignedToken({token:accessToken,pathname,operations:['get'],validUntil:until});
   const {presignedUrl}=await presignUrl(token,{operation:'get',pathname,validUntil:until});
   return res.status(200).json({url:presignedUrl,expiresIn:900});
 }
 return res.status(400).json({error:'Ação inválida'});
 }catch(e){return res.status(400).json({error:e?.message==='Armazenamento privado não conectado'?e.message:'Ação não autorizada ou arquivo inválido'});}
}
