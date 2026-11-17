import base64, hashlib, hmac, json, os, time
from urllib.parse import urlsplit
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from .publication_forms import VlogPostForm
from .models import VlogVideo, User
from .access_control import can_manage_clinic


def _can_publish(user):
    return user.is_authenticated and user.is_active and (user.role == User.ADMIN or (user.role == User.STAFF and user.staff_job == User.JOB_DOCTOR and user.is_staff))

def _guard(request):
    if not request.user.is_authenticated:
        return redirect('professional_login')
    if not _can_publish(request.user):
        raise PermissionDenied('Publicações restritas à profissional autorizada.')
    if getattr(request.user,'must_change_password', False):
        return redirect('/gestao/password_change/')
    return None

def login_view(request):
    if request.user.is_authenticated and request.user.is_active and request.user.role in (User.STAFF, User.ADMIN):
        return redirect('master_access' if can_manage_clinic(request.user) else 'professional_access_home')
    form=AuthenticationForm(request, data=request.POST or None)
    if request.method=='POST' and form.is_valid():
        user=form.get_user()
        if not user.is_active or user.role not in (User.STAFF, User.ADMIN):
            form.add_error(None, 'Esta conta não possui autorização de acesso.')
        else:
            login(request, user)
            if getattr(user, 'must_change_password', False):
                return redirect('/gestao/password_change/')
            return redirect('master_access' if can_manage_clinic(user) else 'professional_access_home')
    return render(request,'clinic/professional_login.html',{'form':form})

def logout_view(request):
    if request.method=='POST':
        logout(request)
        return redirect('professional_login')
    return redirect('professional_posts')

def list_view(request):
    gate=_guard(request)
    if gate:return gate
    posts=VlogVideo.objects.all()[:200]
    return render(request,'clinic/professional_posts.html',{'posts':posts,'now':timezone.now(), 'live_count':VlogVideo.objects.filter(published=True,publish_at__lte=timezone.now()).count()})

def edit_view(request,pk=None):
    gate=_guard(request)
    if gate:return gate
    post=get_object_or_404(VlogVideo,pk=pk) if pk else None
    form=VlogPostForm(request.POST or None,instance=post,initial={'published': True} if not post and request.method != 'POST' else None)
    if request.method=='POST' and form.is_valid():
        submitted_path=form.cleaned_data.get('private_media_path','') or ''
        if submitted_path and submitted_path != (post.private_media_path if post else ''):
            if not submitted_path.startswith(f'vlog/private/{request.user.pk}/'):
                form.add_error('private_media_path','A mídia precisa ter sido enviada pela sua sessão.')
        if form.errors:
            return render(request,'clinic/professional_post_form.html',{'form':form,'post':post,'blob_available':bool(os.getenv('BLOB_READ_WRITE_TOKEN')), 'private_blob_available':bool(os.getenv('VLOG_PRIVATE_READ_WRITE_TOKEN')), 'upload_authorization':media_authorization(request.user)})
        obj=form.save(commit=False)
        if not obj.slug:
            s=slugify(obj.title)[:150] or 'publicacao'; stem=s; i=2
            while VlogVideo.objects.filter(slug=s).exclude(pk=obj.pk).exists():
                s=f'{stem}-{i}';i+=1
            obj.slug=s
        obj.save()
        messages.success(request,'Publicação enviada para Tirando Dúvidas.' if obj.published and obj.publish_at <= timezone.now() else ('Publicação programada para Tirando Dúvidas.' if obj.published else 'Rascunho salvo. Não aparece no site público.'))
        return redirect('professional_posts')
    return render(request,'clinic/professional_post_form.html',{'form':form,'post':post,'blob_available':bool(os.getenv('BLOB_READ_WRITE_TOKEN')), 'private_blob_available':bool(os.getenv('VLOG_PRIVATE_READ_WRITE_TOKEN')), 'upload_authorization':media_authorization(request.user)})

@require_POST
def delete_view(request,pk):
    gate=_guard(request)
    if gate:return gate
    post=get_object_or_404(VlogVideo,pk=pk)
    post.published=False
    post.save(update_fields=['published','updated_at'])
    messages.success(request,'Postagem retirada do site público. O conteúdo continua disponível na administração.')
    return redirect('professional_posts')

def media_authorization(user):
    """A signed authorization to generate a short-lived upload token in the Node API."""
    if not _can_publish(user):return ''
    timestamp=str(int(time.time()))
    payload=base64.urlsafe_b64encode(f'{user.pk}:{timestamp}'.encode()).decode().rstrip('=')
    sig=hmac.new(settings.SECRET_KEY.encode(),payload.encode(),hashlib.sha256).hexdigest()
    return f'{payload}.{sig}'

@require_POST
def media_signature(request):
    gate=_guard(request)
    if gate:return gate
    return JsonResponse({'authorization':media_authorization(request.user)})
