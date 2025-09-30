# crudapp/templatetags/extras.py

from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Access a dictionary value in template."""
    return dictionary.get(key)

