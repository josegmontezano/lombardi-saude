from django import forms
from django.utils.text import slugify
from .models import VlogVideo

class VlogPostForm(forms.ModelForm):
    class Meta:
        model=VlogVideo
        fields=['title','category','summary','body','video_url','media_url','private_media_path','cover_url','published','featured']
        widgets={'summary':forms.Textarea(attrs={'rows':3,'placeholder':'Resumo que aparece na listagem'}),'body':forms.Textarea(attrs={'rows':17,'placeholder':'Escreva sua reportagem, sem limite editorial de caracteres. Separe os parágrafos com Enter.'}),'video_url':forms.URLInput(attrs={'placeholder':'https://youtu.be/... ou outro link aceito'}),'media_url':forms.HiddenInput(),'private_media_path':forms.HiddenInput(),'cover_url':forms.HiddenInput()}
    def clean(self):
        data=super().clean()
        if not (data.get('body') or data.get('video_url') or data.get('media_url') or data.get('private_media_path')):
            raise forms.ValidationError('Escreva um texto ou inclua um vídeo.')
        if not data.get('summary'):
            data['summary']=(data.get('body') or data.get('title') or '')[:300]
        return data
