def notifications(request):
    if not request.user.is_authenticated:
        return {"nb_notifications": 0, "notifications_liste": []}

    from dashboard.models import Notification

    notifs = Notification.objects.filter(
        destinataire=request.user, lu=False, archive=False, supprimee=False
    ).select_related("client", "recommandation").order_by("-date_creation")

    nb = notifs.count()
    notifs_liste = notifs[:15]

    return {"nb_notifications": nb, "notifications_liste": notifs_liste}
