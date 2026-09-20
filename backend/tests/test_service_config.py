import unittest

from services.service_config import normalize_service_key, resolve_service_url


class ServiceConfigTests(unittest.TestCase):
    def test_normalize_service_key_keeps_stable_identifier_only(self):
        self.assertEqual(normalize_service_key('  user-center  '), 'user-center')
        self.assertIsNone(normalize_service_key(''))
        self.assertIsNone(normalize_service_key(None))

    def test_missing_service_uses_base_url_and_interface_path(self):
        url, service = resolve_service_url(
            'https://api.example.com',
            '/users/detail',
            {'items': []},
            'user-center',
        )

        self.assertEqual(url, 'https://api.example.com/users/detail')
        self.assertIsNone(service)

    def test_disabled_service_uses_base_url_and_interface_path(self):
        url, service = resolve_service_url(
            'https://api.example.com',
            '/users/detail',
            {'items': [
                {'key': 'user-center', 'path_prefix': '/user', 'enabled': False},
            ]},
            'user-center',
        )

        self.assertEqual(url, 'https://api.example.com/users/detail')
        self.assertIsNone(service)


if __name__ == '__main__':
    unittest.main()

