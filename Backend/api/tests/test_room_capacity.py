from django.test import SimpleTestCase

from api.utils import can_room_accommodate


class RoomCapacityTests(SimpleTestCase):
    def test_room_has_enough_capacity(self):
        result = can_room_accommodate(30, 25)

        self.assertTrue(result)