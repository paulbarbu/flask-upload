import unittest
from mock import MagicMock, patch, Mock


class DatabaseTest(unittest.TestCase):
    '''Tests the database functionality'''

    def test_valid_file(self):
        from index import is_valid_sqlite3

        with patch('index.open', create=True) as mock_open:
            mock_open.return_value = MagicMock(spec=file)
            fh = mock_open.return_value.__enter__.return_value

            fh.read.return_value = 'SQLite format 3'

            self.assertTrue(is_valid_sqlite3('db.db'))
            fh.read.assert_called_with(15)

            fh.read.return_value = 'SQLite format 3 '  # notice the space

            self.assertFalse(is_valid_sqlite3('db.db'))
            fh.read.assert_called_with(15)

    def test_add_user(self):
        from index import add_user
        import err
        import sqlite3

        db = Mock()

        self.assertTrue(add_user(db, 'foo', 'bar@baz.qux', 'password'))

        db.execute.side_effect = sqlite3.IntegrityError('email')
        self.assertEqual(add_user(db, 'foo', 'bar@baz.qux', 'password'),
                err.UNIQUE_EMAIL)

        db.execute.side_effect = sqlite3.IntegrityError('nick')
        self.assertEqual(add_user(db, 'foo', 'bar@baz.qux', 'password'),
                err.UNIQUE_NICK)

        db.execute.side_effect = sqlite3.IntegrityError('foobar')
        self.assertFalse(add_user(db, 'foo', 'bar@baz.qux', 'password'))

        db.execute.side_effect = Exception()
        self.assertFalse(add_user(db, 'foo', 'bar@baz.qux', 'password'))

    def test_get_user_id(self):
        from index import get_user_id

        db = Mock()
        db.fetchone.return_value = None

        self.assertIsNone(get_user_id(db, 'foo', 'pass'))

        db.fetchone.return_value = (42,)
        self.assertEqual(get_user_id(db, 'foo', 'pass'), 42)

        db.execute.side_effect = Exception('')
        self.assertFalse(get_user_id(db, 'foo', 'pass'))

    def test_get_nick_by_id(self):
        from index import get_nick_by_id

        db = Mock()
        db.fetchone.return_value = None

        self.assertIsNone(get_nick_by_id(db, 42))

        db.fetchone.return_value = ('foo',)
        self.assertEqual(get_nick_by_id(db, 42), 'foo')

        db.execute.side_effect = Exception()
        self.assertFalse(get_nick_by_id(db, 42))


if __name__ == "__main__":
    unittest.main()
