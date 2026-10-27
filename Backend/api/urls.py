from django.urls import path
from . import views

urlpatterns = [
    path("rooms/", views.RoomListAPIView.as_view(), name="room-list"),
    path("rooms/available-slots/", views.AvailableSlotsAPIView.as_view(), name="available-slots"),
    path("rooms/<uuid:pk>/", views.RoomDetailAPIView.as_view(), name="room-detail"),
    path("bookings/", views.BookingListCreateAPIView.as_view(), name="booking-list-create"),
    path("bookings/<uuid:pk>/", views.BookingDetailAPIView.as_view(), name="booking-detail"),
    path("bookings/<uuid:pk>/change/", views.BookingChangeRoomAPIView.as_view(), name="booking-change-room"),
    path("users/me/bookings/", views.UserBookingsAPIView.as_view(), name="user-bookings"),
    path("sync-logs/", views.SyncLogListAPIView.as_view(), name="sync-log-list"),
    path("sync/", views.SyncTriggerAPIView.as_view(), name="sync-trigger"),
]
