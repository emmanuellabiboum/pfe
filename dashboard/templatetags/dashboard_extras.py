from django import template

register = template.Library()


@register.filter
def sub(value, arg):
    """Soustraction template"""
    try:
        return float(value) - float(arg)
    except:
        return 0
