from django import forms
from .models import VisitorSubmission

class PublicMessageForm(forms.ModelForm):
    privacy_ack = forms.BooleanField(label='Li o aviso de privacidade e autorizo o tratamento dos dados para responder à solicitação.', required=True)
    publish_authorized = forms.BooleanField(label='Autorizo a publicação do meu texto após revisão pela Lombardi Saúde (opcional).', required=False)
    show_name = forms.BooleanField(label='Se publicado, autorizo exibir meu primeiro nome (opcional).', required=False)
    homepage = forms.CharField(required=False, widget=forms.TextInput(attrs={'tabindex':'-1','autocomplete':'off','aria-hidden':'true'}))
    class Meta:
        model = VisitorSubmission
        fields = ('kind','name','email','text','publish_authorized','show_name','privacy_ack','homepage')
        widgets = {'text': forms.Textarea(attrs={'rows':7, 'maxlength':5000, 'placeholder':'Escreva sua dúvida ou mensagem. Não envie exames, CPF, dados clínicos ou outras informações sensíveis.'})}
        labels = {'kind':'Quero enviar', 'name':'Seu nome', 'email':'Seu e-mail (não será publicado)', 'text':'Sua mensagem ou dúvida'}
    def clean(self):
        data=super().clean()
        if data.get('homepage'):
            raise forms.ValidationError('Não foi possível enviar. Tente novamente.')
        text=data.get('text', '').strip()
        if len(text) < 15:
            self.add_error('text', 'Escreva pelo menos 15 caracteres.')
        if data.get('show_name') and not data.get('publish_authorized'):
            self.add_error('show_name', 'Autorize também a publicação para exibir o nome.')
        return data

class ModerationForm(forms.ModelForm):
    class Meta:
        model=VisitorSubmission
        fields=('status','answer')
        widgets={'answer':forms.Textarea(attrs={'rows':9,'placeholder':'Resposta revisada pela clínica. Não publique dados identificáveis ou orientações médicas individualizadas.'})}
        labels={'status':'Decisão','answer':'Resposta oficial (quando aplicável)'}
