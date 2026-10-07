from django.urls import path
from . import views

urlpatterns = [
    path('rooms/', views.RoomListAPIView.as_view(), name='room-list'),
    path('rooms/available-slots/', views.AvailableSlotsAPIView.as_view(), name='available-slots'),
    path('bookings/', views.BookingListCreateAPIView.as_view(), name='booking-list-create'),
    path('bookings/<int:pk>/', views.BookingDetailAPIView.as_view(), name='booking-detail'),
    path('users/me/bookings/', views.UserBookingsAPIView.as_view(), name='user-bookings'),
]

