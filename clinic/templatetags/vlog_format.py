"""Escaped, semantic article formatting; author can use ## headings and bullet lines."""
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter(name="vlog_article")
def vlog_article(value):
    if not value:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    result = []
    paragraph = []
    bullets = []

    def close_paragraph():
        if paragraph:
            result.append('<p>' + '<br>'.join(escape(line) for line in paragraph) + '</p>')
            paragraph.clear()

    def close_bullets():
        if bullets:
            result.append('<ul>' + ''.join('<li>' + escape(x) + '</li>' for x in bullets) + '</ul>')
            bullets.clear()

    for raw in text.split('\n'):
        line = raw.strip()
        if not line:
            close_paragraph()
            close_bullets()
        elif line.startswith('## '):
            close_paragraph()
            close_bullets()
            result.append('<h2>' + escape(line[3:]) + '</h2>')
        elif line.startswith('### '):
            close_paragraph()
            close_bullets()
            result.append('<h3>' + escape(line[4:]) + '</h3>')
        elif line.startswith('- '):
            close_paragraph()
            bullets.append(line[2:])
        else:
            close_bullets()
            paragraph.append(line)
    close_paragraph()
    close_bullets()
    return mark_safe('\n'.join(result))
