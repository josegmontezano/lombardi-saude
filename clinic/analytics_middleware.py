"""Anonymous, opt-in page visit measurement: no IP addresses stored."""
import hashlib
import re
from urllib.parse import unquote
from django.core import signing
from django.utils.deprecation import MiddlewareMixin

EXCLUDE_PREFIXES = ('/static/', '/api/', '/profissional/', '/gestao/', '/interno/', '/saude/', '/privacidade/estatisticas/', '/paciente/', '/funcionario/')
BOTS = re.compile(r'bot|spider|crawler|healthcheck|monitor|preview|headless', re.I)

class ConsentAnalyticsMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if (request.method != 'GET' or response.status_code != 200 or
            request.path.startswith(EXCLUDE_PREFIXES) or
            request.COOKIES.get('lx_stats') != 'accepted' or
            BOTS.search(request.headers.get('User-Agent', ''))):
            return response
        try:
            visitor = signing.loads(request.COOKIES.get('lx_visitor',''), salt='lx-stats', max_age=120*24*3600)
            if not isinstance(visitor, str) or len(visitor) != 36:
                return response
            token = hashlib.sha256(visitor.encode('ascii')).hexdigest()
            from .models import WebsiteVisit
            WebsiteVisit.objects.create(
                page_path=request.path[:240], visitor_token=token,
                country=request.headers.get('X-Vercel-IP-Country', '')[:3].upper(),
                region=request.headers.get('X-Vercel-IP-Country-Region', '')[:6].upper(),
                city=unquote(request.headers.get('X-Vercel-IP-City', ''))[:100],
            )
        except Exception:
            # Analytics must never interrupt the public website.
            pass
        return response
