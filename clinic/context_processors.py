"""No patient or staff portal notifications on the institutional website."""
def notification_bell(request):
    return {'bell_visible': False}
