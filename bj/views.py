from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views.generic import TemplateView


# def blackjack(request):
#     return render(request, 'test.html')

class CreateRoomView(TemplateView):
    template_name = 'create_room.html'

    def post(self, request, *args, **kwargs):
        room_name = request.POST.get('room_name')
        if room_name:
            return redirect('blackjack', room_name=room_name)


def blackjack(request, room_name):
    return render(request, 'test.html', {'room_name': room_name})
