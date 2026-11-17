"""Content publishing administration for the institutional Lombardi Saúde site."""
from django.contrib import admin
from django.contrib.auth.models import Group
from .models import VlogVideo, WebsiteVisit, VisitorSubmission, InstagramEntry, ClinicReview, StaffAccessRequest

try: admin.site.unregister(Group)
except admin.sites.NotRegistered: pass

@admin.register(VlogVideo)
class VlogVideoAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'published', 'featured', 'publish_at', 'updated_at')
    list_filter = ('published', 'category', 'featured')
    search_fields = ('title', 'summary')
    prepopulated_fields = {'slug': ('title',)}
    list_editable = ('published', 'featured')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Conteúdo destinado ao Tirando Dúvidas', {'fields': ('title', 'slug', 'category', 'summary', 'body', 'video_url', 'cover_url', 'media_url')}),
        ('Publicação automática em Tirando Dúvidas', {'fields': ('published', 'featured', 'publish_at')}),
        ('Histórico', {'fields': ('created_at', 'updated_at')}),
    )

admin.site.site_header = 'Lombardi Saúde · Vlog'
admin.site.site_title = 'Publicações — Lombardi Saúde'
admin.site.index_title = 'Gerenciar vídeos educativos'


@admin.register(WebsiteVisit)
class WebsiteVisitAdmin(admin.ModelAdmin):
    list_display = ('created_at','page_path','country','region','city')
    list_filter = ('country',)
    readonly_fields = ('created_at','page_path','visitor_token','country','region','city')
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(VisitorSubmission)
class VisitorSubmissionAdmin(admin.ModelAdmin):
    list_display = ('kind','name','created_at','status','publish_authorized')
    list_filter = ('kind','status')
    search_fields = ('name','email','text')
    readonly_fields = ('kind','name','email','text','publish_authorized','show_name','privacy_ack','created_at')
    fields = ('kind','name','email','text','created_at','publish_authorized','show_name','privacy_ack','status','answer')
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(InstagramEntry)
class InstagramEntryAdmin(admin.ModelAdmin):
    list_display = ('kind','instagram_id','posted_at','synced_at')
    readonly_fields = ('instagram_id','kind','caption','permalink','media_url','thumbnail_url','posted_at','expires_at','synced_at')
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(ClinicReview)
class ClinicReviewAdmin(admin.ModelAdmin):
    list_display = ("created_at", "unit", "patient_name", "status", "reception", "nursing_technician", "nursing", "doctor")
    list_filter = ("unit", "status", "created_at")
    readonly_fields = ("created_at", "unit", "patient_name", "patient_email", "patient_phone", "status", "reviewed_by", "reviewed_at", "reception", "nursing_technician", "nursing", "doctor", "private_comment")
    fields = readonly_fields
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(StaffAccessRequest)
class StaffAccessRequestAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "requested_job", "status", "reviewed_by", "reviewed_at")
    list_filter = ("status", "requested_job")
    readonly_fields = ("created_at", "user", "requested_job", "status", "reviewed_by", "reviewed_at")
    fields = readonly_fields
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
