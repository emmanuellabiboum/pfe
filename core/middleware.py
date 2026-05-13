from django.shortcuts import redirect
from django.http import JsonResponse
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.messages import get_messages


class AgenceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and not request.user.is_superuser
            and request.user.role not in ["admin", "super_admin"]
            and not hasattr(request.user, "agence")
        ):
            # Pour les requêtes AJAX, retourner une réponse JSON au lieu de rediriger
            if (
                request.headers.get("X-Requested-With") == "XMLHttpRequest"
                or request.headers.get("Accept", "").find("application/json") != -1
            ):
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Utilisateur non associé à une agence. Veuillez assigner une agence.",
                        "redirect": True,
                        "redirect_url": "/accounts/assign-agence/",
                    },
                    status=403,
                )
            return redirect("accounts:assign_agence")
        return self.get_response(request)


class MessageFilterMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/login/" or request.path == "/accounts/login/":
            storage = FallbackStorage(request)
            list(get_messages(request))

        response = self.get_response(request)
        return response
