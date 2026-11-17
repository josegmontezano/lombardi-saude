"""Lombardi Saúde — site institucional e Vlog. Portais legados despublicados."""
from django.contrib import admin
from django.urls import path, re_path
from django.http import HttpResponseGone
from django.views.generic import RedirectView
from clinic import community_views as community
from clinic import views
from clinic import review_views as reviews
from clinic import professional_views as pro
from clinic import access_views as access

def former_portal(request, *args, **kwargs):
    response = HttpResponseGone('Esta área foi desativada. Acesse Contato para falar com a Lombardi Saúde.', content_type='text/plain; charset=utf-8')
    response['Cache-Control'] = 'no-store'
    return response

urlpatterns = [
    path('', views.home, name='home'),
    path('sobre/', views.about, name='about'),
    path('especialidades/', views.specialties, name='specialties'),
    path('tecnologia/', former_portal),
    path('servicos/', RedirectView.as_view(pattern_name='specialties', permanent=True), name='services'),
    path('conteudos/', views.content, name='content'),
    path('duvidas/', RedirectView.as_view(url='/vlog/#enviar-duvida', permanent=False), name='community'),
    path('duvidas/enviar/', community.submit, name='community_submit'),
    path('instagram/', community.instagram_feed, name='instagram_feed'),
    path('privacidade/estatisticas/', community.analytics_consent, name='analytics_consent'),
    path('profissional/indicadores/', community.professional_analytics, name='professional_analytics'),
    path('profissional/duvidas/', community.professional_submissions, name='professional_submissions'),
    path('profissional/duvidas/<int:pk>/', community.professional_submission_edit, name='professional_submission_edit'),
    path('profissional/instagram/', community.professional_instagram, name='professional_instagram'),
    path('profissional/instagram/<int:pk>/remover/', community.professional_instagram_remove, name='professional_instagram_remove'),
    path('vlog/', views.vlog_index, name='vlog_index'),
    path('vlog/<slug:slug>/', views.vlog_detail, name='vlog_detail'),
    path('avaliacoes/', reviews.review_page, name='review_page'),
    path('avaliacoes/enviar/', reviews.review_submit, name='review_submit'),
    path('avaliacoes/indicadores/', reviews.review_public_data, name='review_public_data'),
    path('gestao/avaliacoes/', reviews.review_dashboard, name='review_dashboard'),
    path('profissional/avaliacoes/', reviews.review_moderation, name='review_moderation'),
    path('profissional/avaliacoes/<int:pk>/decidir/', reviews.review_decision, name='review_decision'),
    path('contato/', views.contact, name='contact'),
    path('privacidade/', views.privacy, name='privacy'),
    path('profissional/entrar/', pro.login_view, name='professional_login'),
    path('profissional/cadastro/', access.signup, name='professional_signup'),
    path('profissional/cadastro/recebido/', access.signup_received, name='professional_signup_received'),
    path('profissional/painel/', access.professional_access_home, name='professional_access_home'),
    path('profissional/mestre/', access.master_access, name='master_access'),
    path('gestao/password_change/', access.professional_password_change, name='professional_password_change'),
    path('profissional/gestao/', access.management_access, name='management_access'),
    path('profissional/gestao/<int:pk>/decidir/', access.management_decision, name='management_decision'),
    path('profissional/sair/', pro.logout_view, name='professional_logout'),
    path('profissional/publicacoes/', pro.list_view, name='professional_posts'),
    path('profissional/publicacoes/nova/', pro.edit_view, name='professional_post_new'),
    path('profissional/publicacoes/<int:pk>/editar/', pro.edit_view, name='professional_post_edit'),
    path('profissional/publicacoes/<int:pk>/excluir/', pro.delete_view, name='professional_post_delete'),
    path('profissional/midia/assinar/', pro.media_signature, name='professional_media_signature'),
    path('gestao/', admin.site.urls),
    path('saude/', views.healthcheck, name='healthcheck'),
    re_path(r'^(?:paciente|funcionario|notificacoes)(?:/.*)?$', former_portal),
    path('sair/', former_portal),
]
