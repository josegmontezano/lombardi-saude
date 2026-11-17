"""Institutional community, editorial moderation, privacy analytics and Instagram."""
import hmac
import os
import uuid
from datetime import timedelta, datetime, time
from zoneinfo import ZoneInfo
from django.conf import settings
from django.contrib import messages
from django.core import signing
from django.db.models import Count
from django.db.models.functions import TruncDate, ExtractHour
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST, require_GET
from .models import VisitorSubmission, InstagramEntry, WebsiteVisit
from .community_forms import PublicMessageForm, ModerationForm
from .professional_views import _guard


SP = ZoneInfo('America/Sao_Paulo')


def community(request):
    published = VisitorSubmission.objects.filter(status='published', publish_authorized=True).order_by('-created_at')[:50]
    return render(request, 'clinic/community.html', {'form':PublicMessageForm(), 'submissions':published})


@require_POST
def submit(request):
    form=PublicMessageForm(request.POST)
    if form.is_valid():
        email=form.cleaned_data['email'].strip().lower()
        # Field-level anti-spam plus per-email rate limit (no visitor IP stored).
        since=timezone.now()-timedelta(hours=1)
        if VisitorSubmission.objects.filter(email__iexact=email,created_at__gte=since).count() >= 3:
            form.add_error(None,'Limite temporário de mensagens. Aguarde antes de enviar novamente.')
        else:
            item=form.save(commit=False)
            item.name=item.name.strip()
            item.email=email
            item.status='pending'
            item.save()
            messages.success(request,'Mensagem recebida! Nossa equipe revisará antes de responder ou publicar.')
            return redirect('/vlog/#enviar-duvida')
    published=VisitorSubmission.objects.filter(status='published',publish_authorized=True).order_by('-created_at')[:50]
    from .models import VlogVideo
    return render(request,'clinic/vlog.html',{
        'form':form,'submissions':published,
        'videos':VlogVideo.objects.filter(published=True,publish_at__lte=timezone.now()),
        'categories':VlogVideo.CATEGORIES,'selected_category':'',
    },status=400)


@require_POST
def analytics_consent(request):
    choice=request.POST.get('consent')
    if choice not in ('yes','no'):return HttpResponseForbidden('Escolha inválida.')
    response=redirect('home')
    response.set_cookie('lx_stats','accepted' if choice=='yes' else 'declined', max_age=120*86400,
                        secure=not settings.DEBUG, httponly=True,samesite='Lax')
    if choice=='yes':
        visitor=str(uuid.uuid4())
        response.set_cookie('lx_visitor',signing.dumps(visitor,salt='lx-stats'),max_age=120*86400,
                            secure=not settings.DEBUG,httponly=True,samesite='Lax')
    else:
        response.delete_cookie('lx_visitor',samesite='Lax')
    return response


def instagram_feed(request):
    # Public posts added by the authorized clinic team. No Instagram account API.
    from django.core.paginator import Paginator
    qs = InstagramEntry.objects.filter(instagram_id__startswith='manual:').exclude(
        kind='STORY').order_by('-posted_at', '-id')
    page = Paginator(qs, 20).get_page(request.GET.get('pagina', 1))
    return render(request, 'clinic/instagram_feed.html', {
        'posts': page.object_list, 'page_obj': page, 'total_posts': page.paginator.count,
        'per_page': 20,
        'empty_slots': list(range((page.number - 1) * 20 + len(page.object_list) + 1, page.number * 20 + 1)),
    })


def _pro(request):
    return _guard(request)


def professional_analytics(request):
    gate=_pro(request)
    if gate:return gate
    now=timezone.now()
    periods={'h24':now-timedelta(hours=24),'d7':now-timedelta(days=7),
             'd15':now-timedelta(days=15),'d30':now-timedelta(days=30)}
    stats={}
    for key,date in periods.items():
        q=WebsiteVisit.objects.filter(created_at__gte=date)
        stats[key]={'views':q.count(), 'visitors':q.exclude(visitor_token='').values('visitor_token').distinct().count()}
    views=WebsiteVisit.objects.filter(created_at__gte=periods['d30'])
    hours={x['h']:x['n'] for x in views.annotate(h=ExtractHour('created_at',tzinfo=SP)).values('h').annotate(n=Count('id'))}
    daymap={x['d'].isoformat():x['n'] for x in views.annotate(d=TruncDate('created_at',tzinfo=SP)).values('d').annotate(n=Count('id'))}
    days=[]
    start=timezone.localtime(now,SP).date()
    for offset in range(29,-1,-1):
        day=start-timedelta(days=offset)
        days.append({'date':day.strftime('%d/%m'),'count':daymap.get(day.isoformat(),0)})
    hist=[{'hour':str(h).zfill(2)+':00','count':hours.get(h,0)} for h in range(24)]
    def geo(key):
        return list(views.exclude(**{key:''}).values(key).annotate(total=Count('id')).order_by('-total',key)[:12])
    return render(request,'clinic/professional_analytics.html',{
        'stats':stats,'hours':hist,'days':days, 'countries':geo('country'),'regions':geo('region'),
        'cities':geo('city'),'most_busy_days':sorted(days,key=lambda x:x['count'],reverse=True)[:10],
        'most_busy_hours':sorted(hist,key=lambda x:x['count'],reverse=True)[:5],
        'started_at':WebsiteVisit.objects.order_by('created_at').values_list('created_at',flat=True).first(),
    })


def professional_submissions(request):
    gate=_pro(request)
    if gate:return gate
    return render(request,'clinic/professional_submissions.html',{
        'submissions':VisitorSubmission.objects.all()[:200],
        'pending_count':VisitorSubmission.objects.filter(status='pending').count(),
    })


def professional_submission_edit(request,pk):
    gate=_pro(request)
    if gate:return gate
    item=get_object_or_404(VisitorSubmission,pk=pk)
    form=ModerationForm(request.POST or None,instance=item)
    if request.method=='POST' and form.is_valid():
        rec=form.save(commit=False)
        try: rec.full_clean()
        except Exception as e:form.add_error(None,str(e))
        else:
            rec.save()
            messages.success(request,'Análise salva. Conteúdo público apenas quando aprovado e autorizado.')
            return redirect('professional_submissions')
    return render(request,'clinic/professional_submission_edit.html',{'form':form,'item':item})


def professional_instagram(request):
    from django import forms
    from urllib.parse import urlsplit
    import re

    class PostLinkForm(forms.Form):
        url = forms.URLField(label='Link público de post ou Reel', max_length=400,
                             widget=forms.URLInput(attrs={'placeholder':'https://www.instagram.com/p/CODIGO/'}))

        def clean_url(self):
            val = (self.cleaned_data['url'] or '').strip()
            parsed = urlsplit(val)
            match = re.fullmatch(r'/(p|reel|tv)/([A-Za-z0-9_-]{5,40})/?', parsed.path)
            if (parsed.scheme != 'https' or parsed.hostname not in ('instagram.com','www.instagram.com')
                    or parsed.username or parsed.password or parsed.port or not match):
                raise forms.ValidationError('Cole um link HTTPS público de post ou Reel do Instagram.')
            return f'https://www.instagram.com/{match.group(1)}/{match.group(2)}/'

    class BulkPostLinkForm(forms.Form):
        links = forms.CharField(
            label='Links públicos de posts e Reels (um por linha)',
            max_length=24000,
            widget=forms.Textarea(attrs={
                'rows':12, 'placeholder':'https://www.instagram.com/p/CODIGO/\nhttps://www.instagram.com/reel/CODIGO/',
                'spellcheck':'false', 'autocomplete':'off',
            }),
            help_text='Cole 20 ou mais links, um por linha. Até 100 por envio. A página mostra 20 por vez.')

        def clean_links(self):
            raw = self.cleaned_data['links']
            lines = [x.strip() for x in raw.splitlines() if x.strip()]
            if len(lines) > 100:
                raise forms.ValidationError('Envie no máximo 100 links por vez.')
            canonical = []
            errors = []
            for i, line in enumerate(lines, start=1):
                field = PostLinkForm({'url':line})
                if not field.is_valid():
                    errors.append(str(i))
                else:
                    canonical.append(field.cleaned_data['url'])
            if errors:
                raise forms.ValidationError(
                    'Links inválidos nas linhas: ' + ', '.join(errors[:20]) +
                    '. Cole somente links HTTPS de posts e Reels.')
            return list(dict.fromkeys(canonical))

    gate = _pro(request)
    if gate: return gate
    is_bulk = request.method == 'POST' and request.POST.get('operation') == 'bulk'
    form = PostLinkForm(request.POST if request.method == 'POST' and not is_bulk else None)
    bulk_form = BulkPostLinkForm(request.POST if is_bulk else None)
    if request.method == 'POST':
        urls = None
        if is_bulk and bulk_form.is_valid():
            urls = bulk_form.cleaned_data['links']
        elif not is_bulk and form.is_valid():
            urls = [form.cleaned_data['url']]
        if urls is not None:
            from django.db import transaction
            added = 0
            with transaction.atomic():
                for url in urls:
                    kind, code = url.split('/')[3:5]
                    marker = f'manual:{kind}:{code}'
                    _, was_created = InstagramEntry.objects.update_or_create(
                        instagram_id=marker,
                        defaults={'kind':'VIDEO' if kind in ('reel','tv') else 'IMAGE',
                                  'caption':'','permalink':url,'media_url':'',
                                  'thumbnail_url':'','posted_at':timezone.now(),
                                  'expires_at':None})
                    added += bool(was_created)
            messages.success(request, f'{len(urls)} links processados; {added} novas publicações adicionadas.')
            return redirect('professional_instagram')
    posts = InstagramEntry.objects.filter(instagram_id__startswith='manual:').exclude(
        kind='STORY').order_by('-posted_at', '-id')[:200]
    total_posts = InstagramEntry.objects.filter(instagram_id__startswith='manual:').exclude(kind='STORY').count()
    return render(request,'clinic/professional_instagram.html',{
        'form':form, 'bulk_form':bulk_form, 'posts':posts, 'total_posts':total_posts,
    })


@require_POST
def professional_instagram_remove(request, pk):
    gate = _pro(request)
    if gate: return gate
    item=get_object_or_404(InstagramEntry,pk=pk,instagram_id__startswith='manual:')
    item.delete()
    messages.success(request,'Publicação retirada do site. O post original do Instagram não foi alterado.')
    return redirect('professional_instagram')
