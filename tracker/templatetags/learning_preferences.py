from django import template
from tracker.preference_bootstrap import preferences_bootstrap_script

register = template.Library()

@register.simple_tag(takes_context=True)
def learning_preferences_bootstrap(context, anonymous=False):
    return preferences_bootstrap_script(None if anonymous else context.get('user'))
