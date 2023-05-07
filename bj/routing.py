from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r'blackjack/(?P<room_name>\w+)/$', consumers.BlackjackGameConsumer.as_asgi()),
]

