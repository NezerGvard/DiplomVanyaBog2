from django import template

register = template.Library()

@register.filter
def replace(value: any, arg):
    new = str(value).replace(arg, "")
    return new